# XMPP MUC Puppet PoC

Due to a quirk (honestly, probably a mistake) XMPP allows a single JID
to become multiple MUC users. Sometimes this happens by accident and is very annoying when your clients get desynced like that.

But for matterbridge, we can exploit this to easily puppet bridge users.

This is a prototype for https://github.com/matterbridge-org/matterbridge/issues/167.

To run, provide credentials:

```
export XMPP_JID=test@example.org
export XMPP_PASSWORD=$(load_password_from_password_manager)
```

Then install and launch:

```
python -m venv .venv
. .venv/bin/activate
pip install -e .
puppetbot \
  puppet1@conference.example.org \
  puppet1@conference.example.org \
  puppet1@conference.example.org \
  puppet2@conference.example.org \
  puppet2@conference.example.org \
  puppet2@conference.example.org \
  puppet3@conference.example.org
```

or faster than `pip`, use `uv`:

```
uv run puppetbot \
  puppet1@conference.example.org \
  puppet1@conference.example.org \
  puppet1@conference.example.org \
  puppet2@conference.example.org \
  puppet2@conference.example.org \
  puppet2@conference.example.org \
  puppet3@conference.example.org
````

Every room given on the command line, **including repeats**, will become a new puppet with a random name, and any message sent in any room (or by DM to $XMPP_JID will be echoed by all the puppets.
