import { createFlow } from '@builderbot/bot';
import { fullSamples } from "./fullSamples.flow";
import { register, main } from "./register.flow";
import {test} from './test.flow';

export const flow = createFlow([register, main, fullSamples, test]);

