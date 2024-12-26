import { Client } from "@langchain/langgraph-sdk";
import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import { join } from 'path'
import { flow } from "flows";
//import { approveFlow } from "./test.flow";

const URL = "http://localhost:8123"

// Store client and thread info per user
const userSessions = new Map<string, {
    client: Client,
    thread: any,
    currentState: any
}>();

export const main = addKeyword(EVENTS.WELCOME)
    .addAction(async (ctx, {flowDynamic}) => {

        if (ctx.body === 'restart') {
            userSessions.clear();
            await flowDynamic('RESTARTED');
            return;
        }

        if (!ctx?.from) {
            console.error('Invalid context or missing user ID');
            return;
        }

        console.log('Running main flow for user:', ctx.from);
        let userSession = userSessions.get(ctx.from);
        
        if (!userSession) {
            console.log('Initializing conversation for new user:', ctx.from);
            const client = new Client({ apiUrl: URL });
            const thread = await client.threads.create();
            userSession = {
                client,
                thread,
                currentState: null
            };
            userSessions.set(ctx.from, userSession);
            // Fix: Pass ctx instead of ctx.body
            await handleNewMessage(userSession, ctx);
        } else {
            if (isConfirmationResponse(ctx.body, userSession.currentState)) {
                await handleConfirmation(userSession, ctx);
            } else if (needsHumanFeedback(userSession.currentState, ctx.body)) {
                await handleHumanFeedback(userSession, ctx);
            } else {
                await handleNewMessage(userSession, ctx);
            }
        }

        await processAndSendResponses(userSession, ctx, flowDynamic);
    });

async function handleNewMessage(userSession: any, ctx: any) {
    const message = ctx.body;
    console.log('Handling new message:', message);
    
    for await (const chunk of userSession.client.runs.stream(
        userSession.thread["thread_id"],
        "task_manager",
        {
            input: { request: message },
            streamMode: "values",
        }
    )) {
        console.log(`Receiving new event of type: ${chunk.event}...`);
        console.log(JSON.stringify(chunk.data, null, 4));
    }

    userSession.currentState = await runAgentAndGetState(userSession);
    userSessions.set(ctx.from, userSession);
}

async function handleConfirmation(userSession: any, ctx: any) {

    let response = ctx.body;

    response = response === 'Si' ? 'Yes' : response;

    await userSession.client.threads.updateState(
        userSession.thread["thread_id"], {
        values: { human_feedback_action_message: response.toLowerCase() }
    });
    userSession.currentState = await runAgentAndGetState(userSession);
    userSessions.set(ctx.from, userSession);
}

async function handleHumanFeedback(userSession: any, ctx: any) {

    const feedback = ctx.body;
    const asNode = userSession.currentState?.next?.[0] === "human_feedback_select" ? "human_feedback_select" : "human_feedback_action";

    console.log('Handling human feedback asNode:', asNode, 'because userSession.currentState?.next?.[0] is ', userSession.currentState?.next?.[0]);

    await userSession.client.threads.updateState(userSession.thread["thread_id"], {
        values: { human_feedback_select_message: feedback },
        asNode: asNode
    });
    userSession.currentState = await runAgentAndGetState(userSession);
    userSessions.set(ctx.from, userSession);
}

async function runAgentAndGetState(userSession: any) {

    console.log('Running agent and getting state...');

    for await (const chunk of userSession.client.runs.stream(
        userSession.thread["thread_id"],
        "task_manager",
        { input: null, streamMode: "values" }
    )) {
            console.log(`Receiving new event of type: ${chunk.event}...`);
            console.log(JSON.stringify(chunk.data, null, 4));
            console.log("\n\n");
    }
    return await userSession.client.threads.getState(userSession.thread["thread_id"]);
}

async function processAndSendResponses(userSession: any, ctx: any, flowDynamic: any) {
    const messages = userSession.currentState?.values?.messages || [];
    const lastHumanIndex = findLastHumanMessageIndex(messages);
    
    if (lastHumanIndex !== -1) {
        await sendNewAIMessages(messages, lastHumanIndex, flowDynamic);
    }

    if (userSession.currentState?.next?.[0] === "human_feedback_select") {
        await flowDynamic([{
            body: 'Confirm procedure?',
            buttons: [{ body: 'Approve' }]
        }]);
    } else if (needsConfirmationButton(userSession.currentState)) {
        await flowDynamic([{
            body: 'Respuesta',
            buttons: [
                { body: 'Si' },
                { body: 'No' }
            ]
        }]);
    }
}

// Helper utility functions
function isConfirmationResponse(body: string, state: any): boolean {
    return (body === "Si" || body === "No") && // Yes or No response
           state?.values?.pending_actions?.length > 0 && // with pending to confirm actions
           !state.values.pending_actions[0].confirmed;
}

function needsHumanFeedback(state: any, body: string): boolean {
    return state?.next?.[0] === "human_feedback_select" || // Human feedback needed to select
            (state?.next?.[0] === "human_feedback_action" && // Human feedback needed to confirm
            body !== "Si" && body !== "No" && // Not a 
            state?.values?.pending_actions?.length > 0 && 
            state.values.pending_actions[0].params == null); // No params filled yet
}

// Find index of last human message in conversation
function findLastHumanMessageIndex(messages: any[]): number {
    //console.log('Searching for last human message in:', messages);
    for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].type === 'human') {
            console.log('Found last human message at index:', i);
            return i;
        }
    }
    console.log('No human messages found');
    return -1;
}

// Send all AI messages that came after the last human message
async function sendNewAIMessages(messages: any[], lastHumanIndex: number, flowDynamic: any) {
    console.log('Sending AI messages after index:', lastHumanIndex);
    for (let i = lastHumanIndex + 1; i < messages.length; i++) {
        const message = messages[i];
        if (message.type === 'ai' && message.name !== 'log') {
            console.log('Sending AI message:', message.content);
            await flowDynamic(message.content);
        }
    }
}

function needsConfirmationButton(state: any): boolean {
    return state?.values?.pending_actions?.some((action: any) => 
        //action.params != null && 
        !action.confirmed
        && state.next[0] === "human_feedback_action"
        && (state.values.pending_actions[0].params != null || state.values.pending_actions[0].params_schema == null)
    ) ?? false;
}




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