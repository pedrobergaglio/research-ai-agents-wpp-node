import { Client } from "@langchain/langgraph-sdk";
import { createBot, createProvider, createFlow, addKeyword, utils, EVENTS } from '@builderbot/bot'
import { MysqlAdapter as Database } from '@builderbot/database-mysql'
import { MetaProvider as Provider } from '@builderbot/provider-meta'
import { join } from 'path'
import { flow } from "flows";
//import { approveFlow } from "./test.flow";

const URL = "http://localhost:7777"
let client = null
let assistants = null
let thread = null
let agent = null
let currentState = null

export const main = addKeyword(EVENTS.WELCOME)
    .addAction(
        async (ctx, {flowDynamic}) => { //

            if (!ctx) {
                console.error('Context (ctx) is undefined');
                return;
            }
            let button_to_send = null;
            console.log('Running main flow');

            if (client === null) { // initialize

                console.log('Initializing conversation');

                client = new Client({ apiUrl: URL });

                // List all assistants
                assistants = await client.assistants.search({
                metadata: null,
                offset: 0,
                limit: 10,
                });
                
                // We auto-create an assistant for each graph you register in config.
                agent = assistants[0];
                
                // Start a new thread
                thread = await client.threads.create();

                const inputDict = {
                    request: ctx.body//"please pay the last bill in gmail"
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
                    //console.log(`Receiving new event of type: ${chunk.event}...`);
                    //console.log(JSON.stringify(chunk.data, null, 4));
                    //console.log("\n\n");
                }
    
                for await (const chunk of client.runs.stream(
                    thread["thread_id"],
                    "task_manager",
                    {
                        input: null,
                        streamMode: "values",
                    }
                )) {
                    //console.log(`Receiving new event of type: ${chunk.event}...`);
                    //console.log(JSON.stringify(chunk.data, null, 4));
                    //console.log("\n\n");
                }

                currentState = await client.threads.getState(thread["thread_id"]);

                if (currentState["next"][0] === "human_feedback_select") {
                    button_to_send = [{body:'Confirm procedure?', 
                        buttons: [
                            {body: 'Approve'},
                        ]
                    }]
                }
            
            } // confirmation
            else if ((ctx.body === "Yes" || ctx.body === "No") && currentState["values"]["pending_actions"].length > 0 && !currentState["values"]["pending_actions"][0]["confirmed"]) {

                console.log('Updating action confirmation:', ctx.body);

                client.threads.updateState(thread["thread_id"], {
                    values: {
                        human_feedback_confirm_message: ctx.body.toLowerCase()
                    },
                    //asNode: "human_feedback_confirm"
                });

                for await (const chunk of client.runs.stream(
                    thread["thread_id"],
                    "task_manager",
                    {
                        input: null,
                        streamMode: "values",
                    }
                )) {
                    //console.log(`Receiving new event of type: ${chunk.event}...`);
                    //console.log(JSON.stringify(chunk.data, null, 4));
                    //console.log("\n\n");
                }
                
                currentState = await client.threads.getState(thread["thread_id"]);

            } // human feedback
            else if (currentState["next"][0] === "human_feedback_select" || 
                (ctx.body != "Yes" && ctx.body != "No" && currentState["values"]["pending_actions"].length > 0 && !currentState["values"]["pending_actions"][0]["confirmed"])
            ) {

                console.log('Selecting human feedback');

                await client.threads.updateState(thread["thread_id"], {
                    values: {
                        human_feedback_select_message: ctx.body
                    },
                    asNode: "human_feedback_select"
                });

                
                for await (const chunk of client.runs.stream(
                    thread["thread_id"],
                    "task_manager",
                    {
                        input: null,
                        streamMode: "values",
                    }
                )) {
                    //console.log(`Receiving new event of type: ${chunk.event}...`);
                    //console.log(JSON.stringify(chunk.data, null, 4));
                    //console.log("\n\n");
                }
                
                currentState = await client.threads.getState(thread["thread_id"]);

                if (currentState["next"][0] === "human_feedback_select") {
                    button_to_send = [{body:'Confirm procedure?', 
                        buttons: [
                            {body: 'Approve'},
                        ]
                    }]
                }


            //} else if(cur){
            
            } else { // new conversation

                console.log('Beginning a new conversation');

                await client.threads.updateState(thread["thread_id"], {
                    values: {
                        request: ctx.body
                    },
                    asNode: "start"
                });
    
                for await (const chunk of client.runs.stream(
                    thread["thread_id"],
                    "task_manager",
                    {
                        input: null,
                        streamMode: "values",
                    }
                )) {
                    //console.log(`Receiving new event of type: ${chunk.event}...`);
                    //console.log(JSON.stringify(chunk.data, null, 4));
                    //console.log("\n\n");
                }

                currentState = await client.threads.getState(thread["thread_id"]);

                if (currentState["next"][0] === "human_feedback_select") {
                    button_to_send = [{body:'Confirm procedure?', 
                        buttons: [
                            {body: 'Approve'},
                        ]
                    }]
                }

            }

            // find the last human message in state[messages]
            let lastHumanMessage = null;
            let lastHumanMessageIndex = -1;
            //console.log("state keys: ", Object.keys(currentState["values"]))
            // send the AI messages to the user
            for (let i = currentState["values"]["messages"].length - 1; i >= 0; i--) {
                if (currentState["values"]["messages"][i]["type"] === "human") {
                    lastHumanMessage = currentState["values"]["messages"][i]["content"];
                    lastHumanMessageIndex = i;
                    break;
                }
            }
            console.log('Last human message:', lastHumanMessage);
            if (lastHumanMessageIndex !== -1) {
                for (let j = lastHumanMessageIndex + 1; j < currentState["values"]["messages"].length; j++) {
                    if (currentState["values"]["messages"][j]["type"] === "ai") {
                        const aiMessage = currentState["values"]["messages"][j]["content"];
                        console.log('AI:', aiMessage);
                        await flowDynamic(aiMessage);
                    }
                } 
            } else {
                console.log('No new AI messages to send');
            }

            console.log("Next: ", currentState["next"]);
            
            if (button_to_send) {
                await flowDynamic(button_to_send)
            } else if (currentState["values"]["pending_actions"].length > 0 
                && currentState["values"]["pending_actions"][0]["params"] != null //filled
                && !currentState["values"]["pending_actions"][0]["confirmed"] //not confirmed
            ) {

                console.log('Confirmation detected for action!');

                //flow_to_go = "confirmFlow";

                await flowDynamic([{body:'Confirm action?', 
                    buttons: [
                        {body: 'Yes'},
                        {body: 'No'},
                    ]
                }])

            }
        }
);


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