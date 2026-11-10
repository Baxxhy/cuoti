import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sameAgentRoute} from '../src/lib/planningRoute.js';
test('agent identity includes both lesson and job',()=>{
 assert(sameAgentRoute({job:'a',lesson:'one'},{job:'a',lesson:'one'}));
 assert(!sameAgentRoute({job:'a',lesson:'one'},{job:'b',lesson:'one'}));
 assert(!sameAgentRoute({lesson:'one'},{lesson:'two'}));
});
