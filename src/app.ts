import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import { setupApi } from './api'; // Adjust the import according to your project structure
import { flow } from 'flows'; // Adjust the import according to your project structure

const PORT = process.env.PORT ?? 3008
const credentials = {
    host: process.env.MYSQL_DB_HOST,
    user: process.env.MYSQL_DB_USER,
    database: process.env.MYSQL_DB_NAME,
    password: process.env.MYSQL_DB_PASSWORD,
    port: 3306,
}
const providerCredentials = {
    jwtToken: process.env.JWT_TOKEN2,
    numberId: process.env.NUMBER_ID,
    verifyToken: process.env.VERIFY_TOKEN,
    version: 'v20.0'
};

const main = async () => {
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