import { createFlow } from '@builderbot/bot';
import { fullSamples } from "./NAfullSamples.flow";
import { main, register } from "./register.flow";
import {approveFlow} from './test.flow';

export const flow = createFlow([register, main, fullSamples, approveFlow]);

