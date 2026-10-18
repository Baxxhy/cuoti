package zhiwei

import std.env.*
import std.collection.*
import std.convert.*
import stdx.log.*
import stdx.encoding.json.*
import stdx.net.http.*

public func algorithmCompute(input: JsonObject, timeoutSeconds!: Int64 = 200, taskBudget!: Option<TaskBudget> = None): JsonObject {
    if (let Some(budget) <- taskBudget) { budget.check("algorithm_start") }
    let endpoint = getVariable("CANGJIE_ALGORITHM_URL") ?? "http://127.0.0.1:8012"
    let secret = getVariable("CANGJIE_ALGORITHM_SECRET") ?? ""
    if (secret.size < 32 || !endpoint.startsWith("http://127.0.0.1:")) { throw ApiError(503, "内部算法服务未配置") }
    try { UInt16.parse(endpoint[17..]) } catch (_: Exception) { throw ApiError(503, "内部算法地址无效") }
    let client = ClientBuilder().noProxy().readTimeout(Duration.second * timeoutSeconds).build()
    client.logger.level = LogLevel.OFF
    try {
        let request = HttpRequestBuilder().method("POST").url(endpoint + "/v1/compute")
            .header("Content-Type", "application/json").header("Authorization", "Bearer " + secret).body(input.toString()).build()
        let response = client.send(request)
        try {
            if (let Some(budget) <- taskBudget) { budget.check("algorithm_response") }
            if (response.status != 200) {
                if (response.status == 502) { throw ApiError(502, "语音计算暂时不可用") }
                if (response.status == 422) { throw ApiError(422, "图片或计算数据无效") }
                throw ApiError(503, "内部算法计算暂时不可用")
            }
            let buffer = Array<UInt8>(65536, repeat: 0)
            // Decode only after all UTF-8 bytes arrive: chunk boundaries may split a rune.
            let bytes = ArrayList<UInt8>()
            while (true) {
                if (let Some(budget) <- taskBudget) { budget.check("algorithm_read") }
                let count = response.body.read(buffer)
                if (let Some(budget) <- taskBudget) { budget.check("algorithm_read") }
                if (count == 0) { break }
                if (bytes.size + count > 128 * 1024 * 1024) { throw ApiError(503, "算法结果过大") }
                bytes.add(all: buffer[..count])
            }
            let payload = (JsonValue.fromStr(String.fromUtf8(bytes.toArray())) as JsonObject).getOrThrow()
            if (jsonText(payload, "operation") != jsonText(input, "operation")) { throw ApiError(503, "算法结果不匹配") }
            return (payload["result"] as JsonObject).getOrThrow()
        } finally { response.close() }
    } catch (error: TaskBudgetExceeded) { throw error }
    catch (error: ApiError) { throw error }
    catch (_: Exception) { throw ApiError(503, "内部算法服务暂时不可用") }
    finally { client.close() }
}
