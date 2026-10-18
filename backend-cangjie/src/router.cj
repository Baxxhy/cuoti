package zhiwei

import std.collection.*
import stdx.net.http.*

// Registration finishes before serve(); request threads only read these maps.
public class ApiDistributor <: HttpRequestDistributor {
    let exact = HashMap<String, HttpRequestHandler>()
    let patterns = ArrayList<(Array<String>, HttpRequestHandler)>()
    let prefixes = ArrayList<(String, HttpRequestHandler)>()

    public func register(path: String, handler: HttpRequestHandler): Unit {
        if (path.endsWith("*")) {
            prefixes.add((path[..path.size - 1], handler))
        } else if (path.contains("{")) {
            patterns.add((path.split("/"), handler))
        } else {
            if (exact.contains(path)) { throw IllegalArgumentException("重复路由") }
            exact.add(path, handler)
        }
    }

    public func distribute(path: String): HttpRequestHandler {
        if (let Some(handler) <- exact.get(path)) { return handler }
        for ((prefix, handler) in prefixes) { if (path.startsWith(prefix)) { return handler } }
        let parts = path.split("/")
        for ((pattern, handler) in patterns) {
            if (parts.size != pattern.size) { continue }
            var matches = true
            for (index in 0..parts.size) {
                let segment = pattern[index]
                if (segment.startsWith("{") && segment.endsWith("}")) {
                    if (parts[index].isEmpty()) { matches = false; break }
                } else if (segment != parts[index]) { matches = false; break }
            }
            if (matches) { return handler }
        }
        return NotFoundHandler()
    }
}
