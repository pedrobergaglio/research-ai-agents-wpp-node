import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import { join } from 'path'

export const register = addKeyword<Provider, Database>(utils.setEvent('REGISTER_FLOW'))
    .addAnswer(`What is your name?`, { capture: true }, async (ctx, { state }) => {
        await state.update({ name: ctx.body })
    })
    .addAnswer('What is your age?', { capture: true }, async (ctx, { state }) => {
        await state.update({ age: ctx.body })
    })
    .addAction(async (_, { flowDynamic, state }) => {
        await flowDynamic(`${state.get('name')}, thanks for your information!: Your age: ${state.get('age')}`)
    })

export const main = addKeyword(EVENTS.WELCOME)
    //.addAnswer('WELCOME')
    .addAction(
        async (ctx) => {

            console.log('Running main flow');
    
            const request = {
                method: "POST",
                body: JSON.stringify({
                    "message": ctx.body,
                    "from": ctx.from
                    }),
                headers: {
                    "Content-Type": "application/json",
                    },
            };

            console.log('Request sent to Agent:', request);

            // Call the chatbot API
            const response = await fetch("http://127.0.0.1:5000/chat", request);
            const response_str = await response.json();
            console.log('Request response:', response_str);
            return
    }
);
