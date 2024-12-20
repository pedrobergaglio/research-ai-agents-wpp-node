import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import { setupApi } from './api'; // Adjust the import according to your project structure
import { flow } from 'flows'; // Adjust the import according to your project structure

const PORT = 3008//process.env.PORT ?? 3008
const credentials = {
    host: process.env.MYSQL_DB_HOST,
    user: process.env.MYSQL_DB_USER,
    database: process.env.MYSQL_SYSTEM_DB_NAME,
    password: process.env.MYSQL_DB_PASSWORD,
    port: 3306,
}
const providerCredentials = {
    jwtToken: process.env.JWT_TOKEN,
    numberId: process.env.NUMBER_ID,
    verifyToken: process.env.VERIFY_TOKEN,
    version: 'v20.0'
};

const main = async () => {

    
    /* const URL = "http://localhost:7777"
    const client = new Client({ apiUrl: URL });
    
    // List all assistants
    const assistants = await client.assistants.search({
      metadata: null,
      offset: 0,
      limit: 10,
    });
    
    // We auto-create an assistant for each graph you register in config.
    const agent = assistants[0];
    
    // Start a new thread
    const thread = await client.threads.create();
    
    const inputDict = {
        request: "please pay the last bill in gmail"
    };
    
    const streamResponse = client.runs.stream(
        thread["thread_id"],
        "task_manager",
        {
            input: inputDict,
            streamMode: "values",
        }
    );
    
    for await (const chunk of streamResponse) {
        console.log(`Receiving new event of type: ${chunk.event}...`);
        console.log(JSON.stringify(chunk.data, null, 4));
        console.log("\n\n");
    }

    for await (const chunk of client.runs.stream(
        thread["thread_id"],
        "task_manager",
        {
            input: null,
            streamMode: "values",
        }
    )) {
        console.log(`Receiving new event of type: ${chunk.event}...`);
        console.log(JSON.stringify(chunk.data, null, 4));
        console.log("\n\n");
    }

    const currentState = await client.threads.getState(thread["thread_id"]);
    console.log(currentState["next"]);
    console.log(currentState["tasks"][0]["interrupts"]);

    return; */





    const adapterProvider = createProvider(Provider, providerCredentials);  
    const adapterDB = new Database(credentials);
    const bot = await createBot({
        flow: flow,
        provider: adapterProvider,
        database: adapterDB,
    });

    bot.httpServer(+PORT);
    setupApi(bot, adapterProvider);
};

main().catch(console.error);