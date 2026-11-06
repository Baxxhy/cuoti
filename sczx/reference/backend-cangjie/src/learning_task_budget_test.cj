package zhiwei

import std.time.*
import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

@Test
class TaskBudgetTest {
    @TestCase
    func allStagesShareRemainingTime() {
        let budget=TaskBudget(started:MonoTime.now()-Duration.second*40)
        let timeout=budget.timeoutSeconds(40,reserveSeconds:1)
        @Expect(timeout>=1 && timeout<=4,true)
        @Expect(budget.elapsedMs()>=40000,true)
        let exhausted=TaskBudget(started:MonoTime.now()-Duration.second*44)
        var rejected=false
        try { exhausted.timeoutSeconds(5,reserveSeconds:1) } catch (_: TaskBudgetExceeded) { rejected=true }
        @Expect(rejected,true)
    }
    @TestCase
    func exhaustedDeadlineDoesNotPermitCommit() {
        let budget=TaskBudget(started:MonoTime.now()-Duration.second*46)
        var rejected=false
        try { budget.check("before_commit") } catch (error: TaskBudgetExceeded) { rejected=error.stage=="before_commit" }
        @Expect(rejected,true)
    }
    @TestCase
    func roundAndExecutionLimitsAreSeparate() {
        for ((rounds,runs,expected) in [(23,71,false),(24,2,true),(3,72,true)]) {
            let task=JsonObject(); let state=JsonObject(); task.put("run_count",JsonInt(runs)); state.put("rounds",JsonInt(rounds)); task.put("checkpoint",state)
            @Expect(taskAtLimit(task),expected)
        }
    }
}
