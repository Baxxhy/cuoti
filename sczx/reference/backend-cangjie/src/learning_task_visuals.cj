package zhiwei

import std.convert.*
import stdx.encoding.json.*

func taskVisualValues(body: JsonObject): JsonObject {
    let raw=body.get("visual_values") ?? JsonObject()
    if (!(raw is JsonObject)) { throw ApiError(422,"图示参数格式不正确") }
    let values=(raw as JsonObject).getOrThrow(); let clean=JsonObject()
    if (values.getFields().size>3) { throw ApiError(422,"图示参数过多") }
    for ((key,value) in values.getFields()) {
        if (!["delta","k","b","a","h"].contains(key) || !(value is JsonInt || value is JsonFloat)) { throw ApiError(422,"包含不支持的图示参数") }
        let number=Float64.parse(value.toString())
        if (!(number>= -100000000.0 && number<=100000000.0)) { throw ApiError(422,"图示参数超出范围") }
        clean.put(key,JsonFloat(number))
    }
    return clean
}

func validateTaskVisualAction(task: JsonObject, body: JsonObject, kind: String, values: JsonObject): Unit {
    if (kind!="observe_visualization" && body.get("visual_values").isSome()) { throw ApiError(422,"当前动作不接受图示参数") }
    if (kind=="visualize" && tutorText(tutorObject(task,"student_view"),"input_kind")!="text") { throw ApiError(409,"请先核对原题再查看图示") }
    if (!["observe_visualization","close_visualization"].contains(kind)) { return }
    let state=tutorObject(task,"checkpoint"); let visual=tutorObject(state,"visualization")
    if (!tutorFlag(state,"visual_open") || visual.getFields().isEmpty() || tutorText(visual,"source_phase")!=tutorText(state,"phase")) { throw ApiError(409,"当前没有可操作的图示，请先打开") }
    if (kind!="observe_visualization") { return }
    let variables=tutorArray(tutorObject(visual,"spec"),"interactive_variables")
    if (values.getFields().size!=variables.getItems().size) { throw ApiError(422,"图示参数与当前图示不匹配") }
    for (item in variables.getItems()) {
        let variable=(item as JsonObject).getOrThrow(); let name=jsonText(variable,"name")
        if (values.get(name).isNone()) { throw ApiError(422,"图示参数与当前图示不匹配") }
        let number=Float64.parse(values[name].toString()); let low=Float64.parse(variable["min"].toString()); let high=Float64.parse(variable["max"].toString()); let step=Float64.parse(variable["step"].toString())
        if (step<=0.0 || number<low || number>high) { throw ApiError(422,"图示参数超出范围") }
        let grid=(number-low)/step; let difference=grid-Float64(Int64(grid+0.5))
        if (difference< -0.0000001 || difference>0.0000001) { throw ApiError(422,"图示参数不符合当前步长") }
    }
}
