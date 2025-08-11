# err-multi-instance-mongodb
Allow multi instances of errbot to run in parallel using mongodb for orchestration to ensure only one bot responds to any given command.

This plugin uses mongodb with a TTL indexes to orchestrate the bot instances and their commands. Why MongoDB? Because my bot already is talking to MongoDB for other purposes, so it makes sense to use it for this as well.

Note that this plugin will cater for Errbot flows, and will ensure that the flows are always executed by the same bot instance due to the context/state that errbot maintains. The downside of this is that if the instance processing the flow goes down, the flow state will be lost and will not be handled by the other instance(s) until the original flow lock is aged out by the TTL flow index.

## Configuration

To use this plugin, you must set the MongoDB URI in your Errbot configuration file (usually `config.py`).

Add the following line to your `config.py`:

```
BOT_MULTI_INSTANCE_MONGODB_URI = "mongodb://username:password@host:port/database.collection"
```

- Replace `username`, `password`, `host`, and `port` with your MongoDB credentials and server details.
- Replace `database.collection` with the name of your database and collection (e.g., `errbot.commands`).
- The URI must include both the database and collection, separated by a dot.

Example:

```
BOT_MULTI_INSTANCE_MONGODB_URI = "mongodb://myuser:mypassword@localhost:27017/errbot.commands"
```

The plugin will automatically create the collection and two TTL indexes if they do not exist. If the indexes already exist, but the ttl differs from the configured values, the indexes will be dropped and recreated with the new TTL values.

There are two indexes, one for non-flow commands and one for flow commands. The TTL is set to 60 seconds for non-flow commands and 5 minutes for flow commands. To override the TTL values, you can set the following configuration options in your `config.py`:

```python
BOT_MULTI_INSTANCE_INDEX_TTL = 60  # TTL for non-flow commands in seconds
BOT_MULTI_INSTANCE_INDEX_FLOW_TTL = 300  # TTL for flow commands in seconds
```

