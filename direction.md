So now we need a rss service that stores the articles in a in-memory database and add a analysis modal hosted llm inference service to access all the articles.

1. Create a RSS polling service that polls the rss feeds and stores the articles in a in-memory database.
2. Create a analysis modal hosted llm inference service to access all the articles. (Model: )
3. Create a message broker to send the articles to the llm inference service.(Use UUID to identify the articles)
4. Run tests for the RSS polling service and analysis modal hosted llm inference service.
