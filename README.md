# err-multi-instance-mongodb
Allow multi instances of errbot to run in parallel using mongodb for orchestration to ensure only one bot responds to any given command.

This plugin uses mongodb with a TTL index to orchestrate the bot instances and their commands.

## Configuration

To use this plugin, you must set the MongoDB URI in your Errbot configuration file (usually `config.py`).

Add the following line to your `config.py`:

```
MULTI_INSTANCE_MONGODB_URI = "mongodb://username:password@host:port/database.collection"
```

- Replace `username`, `password`, `host`, and `port` with your MongoDB credentials and server details.
- Replace `database.collection` with the name of your database and collection (e.g., `errbot.commands`).
- The URI must include both the database and collection, separated by a dot.

Example:

```
MULTI_INSTANCE_MONGODB_URI = "mongodb://myuser:mypassword@localhost:27017/errbot.commands"
```

The plugin will automatically create the collection and a TTL index if they do not exist.
