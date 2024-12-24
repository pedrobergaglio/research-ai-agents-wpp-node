import { Client } from "@langchain/langgraph-sdk";
import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import { join } from 'path'
import { flow } from "flows";
//import { approveFlow } from "./test.flow";

const URL = "http://localhost:7777"

// Store client and thread info per user
const userSessions = new Map<string, {
    client: Client,
    thread: any,
    currentState: any
}>();

export const main = addKeyword(EVENTS.WELCOME)
    .addAction(
        async (ctx, {flowDynamic}) => {
            if (!ctx?.from) {
                console.error('Invalid context or missing user ID');
                return;
            }

            //let button_to_send = null;
            console.log('Running main flow for user:', ctx.from);

            // Get or create user session
            let userSession = userSessions.get(ctx.from);
            
            if (!userSession) { // New user
                console.log('Initializing conversation for new user:', ctx.from);
                
                const client = new Client({ apiUrl: URL });
                /* const assistants = await client.assistants.search({
                    metadata: null,
                    offset: 0,
                    limit: 10,
                }); */
                
                const thread = await client.threads.create();

                console.log('Created new thread:', thread["thread_id"]);

                userSession = {
                    client,
                    thread,
                    currentState: null
                };
                userSessions.set(ctx.from, userSession);

                // Initial message handling
                await handleNewMessage(userSession, ctx.body);
            } else {
                // Existing user conversation handling
                if (isConfirmationResponse(ctx.body, userSession.currentState)) {
                    await handleConfirmation(userSession, ctx.body);
                } else if (needsHumanFeedback(userSession.currentState, ctx.body)) {
                    await handleHumanFeedback(userSession, ctx.body);
                } else {
                    await handleNewMessage(userSession, ctx.body);
                }
            }

            // Process messages and send responses
            await processAndSendResponses(userSession, ctx, flowDynamic);

            const currentState = await userSession?.client?.threads?.getState(userSession?.thread?.["thread_id"]);
            console.log('Current state next:', currentState?.next);
            console.log('Current state interrupts:', currentState?.tasks?.[0]?.interrupts);
        }
    );

// Helper functions
async function handleNewMessage(session: any, message: string) {
    
    console.log('Handling new message:', message);
    
    for await (const chunk of session.client.runs.stream(
        session.thread["thread_id"],
        "task_manager",
        {
            input: {
                request: message
            },
            streamMode: "values",
        }
    )) {
        console.log(`Receiving new event of type: ${chunk.event}...`);
        console.log(JSON.stringify(chunk.data, null, 4));
    }

    session.currentState = await runAgentAndGetState(session);
}

async function handleConfirmation(session: any, response: string) {
    await session.client.threads.updateState(
        session.thread["thread_id"], {
        values: { human_feedback_action_message_message: response.toLowerCase() }
    });
    session.currentState = await runAgentAndGetState(session);
}

async function handleHumanFeedback(session: any, feedback: string) {

    const asNode = session.currentState?.next?.[0] === "human_feedback_select" ? "human_feedback_select" : "human_feedback_action";

    await session.client.threads.updateState(session.thread["thread_id"], {
        values: { human_feedback_select_message: feedback },
        asNode: "human_feedback_select"
    });
    session.currentState = await runAgentAndGetState(session);
}

async function runAgentAndGetState(session: any) {

    console.log('Running agent and getting state...');

    for await (const chunk of session.client.runs.stream(
        session.thread["thread_id"],
        "task_manager",
        { input: null, streamMode: "values" }
    )) {
            console.log(`Receiving new event of type: ${chunk.event}...`);
            console.log(JSON.stringify(chunk.data, null, 4));
            console.log("\n\n");
    }
    return await session.client.threads.getState(session.thread["thread_id"]);
}

async function processAndSendResponses(session: any, ctx: any, flowDynamic: any) {
    const messages = session.currentState?.values?.messages || [];
    const lastHumanIndex = findLastHumanMessageIndex(messages);
    
    if (lastHumanIndex !== -1) {
        await sendNewAIMessages(messages, lastHumanIndex, flowDynamic);
    }

    if (session.currentState?.next?.[0] === "human_feedback_select") {
        await flowDynamic([{
            body: 'Confirm procedure?',
            buttons: [{ body: 'Approve' }]
        }]);
    } else if (needsConfirmationButton(session.currentState)) {
        await flowDynamic([{
            body: 'Confirm action?',
            buttons: [
                { body: 'Yes' },
                { body: 'No' }
            ]
        }]);
    }
}

// Helper utility functions
function isConfirmationResponse(body: string, state: any): boolean {
    return (body === "Yes" || body === "No") && // Yes or No response
           state?.values?.pending_actions?.length > 0 && // with pending to confirm actions
           !state.values.pending_actions[0].confirmed;
}

function needsHumanFeedback(state: any, body: string): boolean {
    return state?.next?.[0] === "human_feedback_select" || // Human feedback needed to select
            (state?.next?.[0] === "human_feedback_action" && // Human feedback needed to confirm
            body !== "Yes" && body !== "No" && // Not a 
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
        if (message.type === 'ai') {
            console.log('Sending AI message:', message.content);
            await flowDynamic(message.content);
        }
    }
}

/* async function handleApproval(session: any) {
    await session.client.threads.updateState(
        session.thread["thread_id"], 
        {
            values: { human_feedback_select_message: "approve" },
            asNode: "human_feedback_select"
        }
    );
    session.currentState = await runAgentAndGetState(session);
} */

/* // Send confirmation buttons to user
async function sendConfirmationButtons(flowDynamic: any) {
    console.log('Sending confirmation buttons');
    await flowDynamic([
        {
            body: 'Would you like to proceed?',
            buttons: [
                { body: 'Yes' },
                { body: 'No' }
            ]
        }
    ]);
} */

function needsConfirmationButton(state: any): boolean {
    return state?.values?.pending_actions?.some((action: any) => 
        //action.params != null && 
        !action.confirmed
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