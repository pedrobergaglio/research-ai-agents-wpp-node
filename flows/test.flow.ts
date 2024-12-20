import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'

const chatHistory: string[] = [];

export const approveFlow = addKeyword<Provider, Database>(['añlsdfkjasldfkj4"'])
    .addAnswer('Confirm procedure?', {
        capture: true, 
        buttons: [
            {body: 'Approve'},
        ]
    })

/* export const test = addKeyword<Provider, Database>(['test']).addAction(
    async (ctx, {flowDynamic}) => {
        // Add the incoming message to the chat history
        console.log('User:', ctx.body);

        const url = "http://127.0.0.1:3008/v1/messages";
        const data = {
            number: ctx.from,
            message: ctx.body
        };
        
        const response = await fetch(url, {
            method: "POST",
            body: JSON.stringify(data),
            headers: {
            "Content-Type": "application/json",
            },
        });



        chatHistory.push(`user: ${ctx.body}`);

        const request = {
            method: "POST",
            body: JSON.stringify(ctx.body),
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
        //await flowDynamic("testFlow");

        // Check the registration status
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
        }
    }
); */