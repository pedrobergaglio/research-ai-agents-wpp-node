import { createFlow } from '@builderbot/bot';
import { fullSamplesFlow } from "./fullSamplesFlow.flow";
import { registerFlow } from "./registerFlow.flow";
import { authentication } from "./authentication.flow";

export const flow =  createFlow([authentication, registerFlow, fullSamplesFlow])

