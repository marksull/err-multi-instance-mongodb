from errbot import BotPlugin
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri
import os


class MongoDBCmdFilterPlugin(BotPlugin):
    def activate(self):
        super().activate()

        mongo_uri = self.bot_config.MONGODB_URI

        if not mongo_uri:
            raise ValueError("MONGODB_URI must be set in the bot configuration.")

        parsed = parse_uri(mongo_uri)
        collection = parsed.get("collection")

        if not collection:
            raise ValueError(
                "MONGODB_URI must specify both database and collection, e.g. /<db>.<collection>"
            )

        self.mongo_client = MongoClient(mongo_uri)
        self.collection = self.mongo_client.get_database()[collection]
        self.bot.add_cmdfilter(self.mongodb_cmdfilter)

    def deactivate(self):
        """
        Deactivate the plugin, removing the command filter and closing the MongoDB connection.
        """
        self.bot.remove_cmdfilter(self.mongodb_cmdfilter)
        self.mongo_client.close()
        super().deactivate()

    def mongodb_cmdfilter(self, msg, cmd, args, dry_run):
        # Store the message in MongoDB for coordination
        self.collection.insert_one(
            {
                "text": str(msg.body),
                "sender": str(msg.frm),
                "to": str(msg.to),
                "cmd": cmd,
                "args": args,
                "dry_run": dry_run,
            }
        )
        # Always allow the command to proceed (coordination logic can be added later)
        return cmd, args, dry_run
