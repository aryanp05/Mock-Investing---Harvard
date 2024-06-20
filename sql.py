from pymongo.mongo_client import MongoClient
uri = "mongodb+srv://aryanpatel0705:8RjhJ29drFuP0NSs@financedb.stlcwww.mongodb.net/?retryWrites=true&w=majority&appName=financedb"
# Create a new client and connect to the server
client = MongoClient(uri)
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)