//import { Bot } from './bot'; // Adjust the import according to your project structure
import { IncomingMessage, ServerResponse } from 'http';
import { isOnlyEmojis, insert_feedback } from 'utils/feedback';
import { check_user_auth } from 'utils/authentication';

let result: any = null;

export const setupApi = (bot: any, adapterProvider: any) => {

    default_setup(bot, adapterProvider);

    adapterProvider.on('message', (ctx) => {
        console.log('Complete Received Message Context:', JSON.stringify(ctx, null, 2));
        result = isOnlyEmojis(ctx.body)
        if (result) {insert_feedback(ctx, result)}

        //console.log('Checking user authentication...', check_user_auth(ctx, result));

        try {
            console.log('Message event triggered');
            console.log('Complete Received Message Context:', JSON.stringify(ctx, null, 2));
            const result = isOnlyEmojis(ctx.body);
            if (result) {
                insert_feedback(ctx, result);
            }
        } catch (error) {
            console.error('Error in message handler:', error);
        }

    });
    

    bot.on('send_message', (ctx) => {
        console.log('Complete Sent Message Context:', JSON.stringify(ctx, null, 2))
    })

    /* server.on('request', async (req: IncomingMessage, res: ServerResponse) => {
        if (req.method === 'POST' && req.url === '/v1/messages') {
            let body = '';
            req.on('data', chunk => {
                body += chunk.toString();
            });
            req.on('end', async () => {
                const { number, message, urlMedia } = JSON.parse(body);
                await bot.sendMessage(number, message, { media: urlMedia ?? null });
                res.end('sended');
            });
        } else if (req.method === 'POST' && req.url === '/v1/register') {
            // Handle registration logic here
            res.end('registered');
        } else if (req.method === 'POST' && req.url === '/v1/sendMessage') {
            let body = '';
            req.on('data', chunk => {
                body += chunk.toString();
            });
            req.on('end', async () => {
                const { number, message, urlMedia } = JSON.parse(body);
                await bot.sendMessage(number, message, { media: urlMedia ?? null });
                res.end('sended');
            });
        } else {
            res.statusCode = 404;
            res.end('Not Found');
        }
    }); */
};

const default_setup = (bot: any, adapterProvider: any) => {
    adapterProvider.server.post(
        '/v1/messages',
        bot.handleCtx(async (bot, req, res) => {
            const { number, message, urlMedia } = req.body
            await bot.sendMessage(number, message, { media: urlMedia ?? null })
            return res.end('sent')
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

    const result: any = null;

    adapterProvider.server.post('/v1/messages', bot.handleCtx(async (bot, req, res) => {
        console.log('Received POST request on /v1/messages');
        const { number, message, urlMedia } = req.body;
        await bot.sendMessage(number, message, { media: urlMedia ?? null });
        return res.end('sent');
    }));
};