import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import mysql from 'mysql2/promise';
import * as fs from 'fs';
import csv from 'csv-parser';
import { isOnlyEmojis, insert_feedback } from 'flows/feedback';
import { check_user_auth } from 'flows/authentication.flow';

const PORT = process.env.PORT ?? 3008

const chatHistory: string[] = [];

const registerFlow = addKeyword<Provider, Database>(['test']).addAction(
    async (ctx, {flowDynamic}) => {
        // Add the incoming message to the chat history
        console.log('User:', ctx.body);
        chatHistory.push(`user: ${ctx.body}`);

        const request = {
            method: "POST",
            body: JSON.stringify(chatHistory),
            headers: {
                "Content-Type": "application/json",
            },
        };
        
        console.log('Request:', request);

        // Call the AI chatbot API with the chat history
        const aiResponse = await fetch("http://127.0.0.1:5000/chat", request);

        const aiMessage = await aiResponse.json();

        // Add the AI response to the chat history
        chatHistory.push(`ai: ${aiMessage}`);

        // Send the AI response to the user
        console.log('AI message:', aiMessage);
        await flowDynamic(aiMessage);

        /* // Check the registration status
        const checkDB = await fetch("http://my.app.example/checkDB", {
            method: "POST",
            body: JSON.stringify({ phoneNumber: ctx.from }),
            headers: {
                "Content-Type": "application/json",
            },
        });

        const status = await checkDB.json();
        if (status === undefined) {
            await state.update({ Registration: false });
            return gotoFlow(unregisteredUsersFlow);
        }
        if (status === true) {
            return gotoFlow(registeredUsersFlow);
        } */
    }
);
    
    
const credentials = {
    host: process.env.MYSQL_DB_HOST,
    user: process.env.MYSQL_DB_USER,
    database: process.env.MYSQL_DB_NAME,
    password: process.env.MYSQL_DB_PASSWORD,
    port: 3306,
}

const main = async () => {
    const adapterFlow = createFlow([registerFlow])
    
    const adapterProvider = createProvider(Provider, {
        jwtToken: process.env.JWT_TOKEN,
        numberId: process.env.NUMBER_ID,
        verifyToken: process.env.VERIFY_TOKEN,
        version: 'v20.0'
    })
    const adapterDB = new Database(credentials)

    const bot = await createBot({
        flow: adapterFlow,
        provider: adapterProvider,
        database: adapterDB,
    })

    adapterProvider.server.post(
        '/v1/messages',
        bot.handleCtx(async (bot, req, res) => {
            const { number, message, urlMedia } = req.body
            await bot.sendMessage(number, message, { media: urlMedia ?? null })
            return res.end('sended')
        })
    )

    adapterProvider.server.post(
        '/v1/register',
        bot.handleCtx(async (bot, req, res) => {
            const { number, name } = req.body
            await bot.dispatch('REGISTER_FLOW', { from: number, name })
            return res.end('trigger')
        })
    )

    adapterProvider.server.post(
        '/v1/samples',
        bot.handleCtx(async (bot, req, res) => {
            const { number, name } = req.body
            await bot.dispatch('SAMPLES', { from: number, name })
            return res.end('trigger')
        })
    )

    adapterProvider.server.post(
        '/v1/blacklist',
        bot.handleCtx(async (bot, req, res) => {
            const { number, intent } = req.body
            if (intent === 'remove') bot.blacklist.remove(number)
            if (intent === 'add') bot.blacklist.add(number)

            res.writeHead(200, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ status: 'ok', number, intent }))
        })
    )

    bot.httpServer(+PORT)

    let result: any = null;

    adapterProvider.on('message', (ctx) => {
        console.log('Complete Received Message Context:', JSON.stringify(ctx, null, 2));
        result = isOnlyEmojis(ctx.body)
        if (result) {insert_feedback(ctx, result)}

        //console.log('Checking user authentication...', check_user_auth(ctx, result));

    });
    

    bot.on('send_message', (ctx) => {
        console.log('Complete Sent Message Context:', JSON.stringify(ctx, null, 2))
    })
}

main()