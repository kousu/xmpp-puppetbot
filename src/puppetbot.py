import os
import logging
import asyncio
import argparse
from itertools import chain

import slixmpp
import slixmpp.xmlstream.xmlstream
import faker
import l33t

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-6s %(name)+25s:%(lineno)d: %(message)s",
)

log = logging.getLogger(__name__)
logging.getLogger("faker.factory").setLevel(logging.WARN)
logging.getLogger("slixmpp.plugins").setLevel(logging.WARN)

class PuppetBot(slixmpp.ClientXMPP):
    """
        The server tracks who is whom by JID resources / streams, and an attempt
        to rejoin a MUC with a new nickname becomes a nick change. But this
        creates a new connection (a new XMPP stream) for each puppet, and that
        allows each to have a new nickname, even in the same room.

        The only way a single stream is allowed to impersonate other JIDs is
        if it is a component (using slixmpp.ComponentXMPP), meaning it has it's
        own domain puppets.example.org, and then it is allowed to impersonante
        anyone@puppets.example.org in DMs, or it is allowed to impersonante
        room@puppets.example.org/anyone. That's good too, but then requires
        the component to become the room that people join, it cannot be bolted
        onto an existing community, and it also means the puppeting bridge is
        also responsible for implementing the full MUC protocol which is vast.
    """
    def __init__(self, jid, password=None):
        super().__init__(jid, password)

        self.register_plugin("xep_0045")

        self.add_event_handler("session_start", self.on_start)
        self.add_event_handler("message", self.on_message)

        # channel -> [nicks]
        self.puppets = {}

        self._fake = faker.Faker()

    async def on_start(self, event):
        self.send_presence()
        await self.get_roster()

    async def join_muc(self, channel: slixmpp.JID):
        await self["xep_0045"].join_muc_wait(channel, self.boundjid.user)

        puppet = slixmpp.ClientXMPP(self.boundjid.bare, self.password)
        puppet.register_plugin("xep_0045")
        puppet.nick = self._fake.name()

        self.puppets.setdefault(str(channel), {})
        self.puppets[str(channel)][puppet.nick] = puppet

        puppet.connect()
        await puppet.wait_until('session_start', timeout=30)
        await puppet["xep_0045"].join_muc_wait(channel, puppet.nick)
        print(f"Joined {channel} as {puppet.nick}")

    async def on_message(self, msg):
        if msg["type"] not in ("chat", "normal", "groupchat"):
            # not a message (it's some metadata that got shoved in <message> over the years)
            return
        if msg["delay"]["stamp"]:
            # scrollback; not a live message; ignore
            return
        if msg["type"] in ("chat","normal") and msg["from"].bare == self.boundjid.bare:
            # print("not talking to ourselves")
            return
        hydra_heads = [self.boundjid.user] + [nick for nicks in self.puppets.values() for nick in nicks]
        if msg["type"] == "groupchat" and msg["from"].resource in hydra_heads:
            # print("not talking to ourselves")
            return

        log.info("Message from %s", msg["from"])

        # echobot x infinity
        #
        for channel, puppets in self.puppets.items():
            for nick, puppet in puppets.items():
                print(f"Echoing message to {channel} as {puppet.nick}")
                puppet.make_message(
                    mtype="groupchat",
                    mto=f"{channel}",
                    mbody=l33t.l33t(msg["body"]),
                ).send()

    def disconnect(self) -> asyncio.Future:
        tasks = []
        for puppets in self.puppets.values():
            for puppet in puppets.values():
                tasks.append(asyncio.ensure_future(puppet.disconnect()))
        tasks.append(asyncio.ensure_future(super().disconnect()))
        return asyncio.ensure_future(asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED))


# -------------------------------------

parser = argparse.ArgumentParser(
    description="""XMPP bot that makes many puppets.
    """,
)
parser.add_argument(
    "channels",
    nargs="+",
    help="Channels to join. Each can be suffixed with ':n' to tell it to create n puppets in that channel",
)


async def amain():
    args = parser.parse_args()

    bot = PuppetBot(os.environ.get("XMPP_JID", ""), os.environ.get("XMPP_PASSWORD", ""))

    try:
        bot.connect()
        login = asyncio.create_task(bot.wait_until("session_start", timeout=30))
        async def connection_failed(event):
           print(f"Unable to connect to {bot.boundjid.bare}'s server.")
           login.cancel()
        async def session_end(event):
           print(f"Unable to login as '{bot.boundjid.bare}'. Check your password.", flush=True)
           login.cancel()
        bot.add_event_handler('connection_failed', connection_failed)
        bot.add_event_handler('session_end', session_end)
        await login
        bot.del_event_handler('connection_failed', connection_failed)
        bot.del_event_handler('session_end', session_end)
        print(f"Logged in as '{bot.boundjid.bare}'")

        # connect the puppets
        # slixmpp.xmlstream.xmlstream.log.setLevel(logging.DEBUG)
        async with asyncio.TaskGroup() as tg:
            for c in args.channels:
                tg.create_task(bot.join_muc(c))

        # block until the bot shuts down
        await bot.disconnected
    except asyncio.CancelledError:
        slixmpp.xmlstream.xmlstream.log.setLevel(logging.WARN)
        await bot.disconnect()


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
