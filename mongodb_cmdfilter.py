from errbot import BotPlugin, botcmd
from errbot.core import ErrBot
from pymongo import MongoClient
import os


class MongoDBCmdFilterPlugin(BotPlugin):

    def activate(self):
        super().activate()
        # Setup MongoDB connection
        mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client['errbot']
        self.collection = self.db['messages']
        # Register the cmdfilter
        self.bot.add_cmdfilter(self.mongodb_cmdfilter)

    def deactivate(self):
        # Remove the cmdfilter and close MongoDB connection
        self.bot.remove_cmdfilter(self.mongodb_cmdfilter)
        self.mongo_client.close()
        super().deactivate()

    def mongodb_cmdfilter(self, msg, cmd, args, dry_run):
        # Store the message in MongoDB for coordination
        self.collection.insert_one({
            'text'   : str(msg.body),
            'sender' : str(msg.frm),
            'to'     : str(msg.to),
            'cmd'    : cmd,
            'args'   : args,
            'dry_run': dry_run,
        })
        # Always allow the command to proceed (coordination logic can be added later)
        return cmd, args, dry_run
