package zhiwei

import std.collection.*
import std.env.*
import std.convert.*
import std.sync.*

foreign {
    func zw_mysql_open(host: CString, port: UInt32, user: CString, password: CString, database: CString): CPointer<UInt8>
    func zw_mysql_close(db: CPointer<UInt8>): Unit
    func zw_mysql_transaction(db: CPointer<UInt8>, operation: Int32): UInt32
    func zw_stmt_prepare(db: CPointer<UInt8>, sql: CString, length: UInt64): CPointer<UInt8>
    func zw_stmt_close(stmt: CPointer<UInt8>): Unit
    func zw_stmt_error(stmt: CPointer<UInt8>): UInt32
    func zw_stmt_param_count(stmt: CPointer<UInt8>): UInt64
    func zw_stmt_bind(stmt: CPointer<UInt8>, index: UInt64, value: CString, length: UInt64, isNull: Int32): Int32
    func zw_stmt_execute(stmt: CPointer<UInt8>): Int32
    func zw_stmt_next(stmt: CPointer<UInt8>): Int32
    func zw_stmt_columns(stmt: CPointer<UInt8>): UInt32
    func zw_stmt_column_name(stmt: CPointer<UInt8>, index: UInt32): CString
    func zw_stmt_value(stmt: CPointer<UInt8>, index: UInt32): CString
    func zw_stmt_length(stmt: CPointer<UInt8>, index: UInt32): UInt64
    func zw_stmt_copy(stmt: CPointer<UInt8>, index: UInt32, output: CPointer<UInt8>, capacity: UInt64): Int32
    func zw_stmt_affected(stmt: CPointer<UInt8>): UInt64
}

class NativeString <: Resource {
    let value: CString
    var closed = false
    init(value: String) { this.value = unsafe { LibC.mallocCString(value) } }
    public func isClosed(): Bool { closed }
    public func close(): Unit {
        if (!closed) { unsafe { LibC.free(value) }; closed = true }
    }
}

public class DatabaseException <: Exception {
    public let code: UInt32
    public init(code: UInt32) {
        super("MySQL 操作失败（${code}）")
        this.code = code
    }
}

public class QueryResult {
    public let rows: ArrayList<HashMap<String, Option<String>>>
    public let affected: UInt64
    init(rows: ArrayList<HashMap<String, Option<String>>>, affected: UInt64) {
        this.rows = rows
        this.affected = affected
    }
}

// A connection is scoped to one request/transaction. No SQL or parameter values
// are included in exceptions. Prepared statements bind every external value.
public class Database <: Resource {
    private var handle: CPointer<UInt8> = CPointer<UInt8>()
    private let mutex = Mutex()
    private var closed = false
    private var inTransaction = false

    public init(host: String, port: UInt32, user: String, password: String, name: String) {
        try (h = NativeString(host), u = NativeString(user), p = NativeString(password), n = NativeString(name)) {
            handle = unsafe { zw_mysql_open(h.value, port, u.value, p.value, n.value) }
        }
        if (handle.isNull()) { throw DatabaseException(2002) }
    }

    public static func fromEnvironment(): Database {
        let name = getVariable("CANGJIE_DB_NAME") ?? "zhiwei_cangjie"
        if (!name.startsWith("zhiwei_cangjie")) {
            throw IllegalArgumentException("仓颉版仅允许使用 zhiwei_cangjie 前缀的独立数据库")
        }
        return Database(getVariable("CANGJIE_DB_HOST") ?? "127.0.0.1",
            UInt32.parse(getVariable("CANGJIE_DB_PORT") ?? "3307"),
            getVariable("CANGJIE_DB_USER") ?? "zhiwei_cangjie",
            getVariable("CANGJIE_DB_PASSWORD") ?? "", name)
    }

    public func isClosed(): Bool { synchronized(mutex) { closed } }
    public func close(): Unit {
        synchronized(mutex) {
            if (!closed) { unsafe { zw_mysql_close(handle) }; closed = true }
        }
    }

    public func query(sql: String): QueryResult { query(sql, []) }

    public func query(sql: String, params: Array<Option<String>>): QueryResult {
        synchronized(mutex) {
            if (closed) { throw DatabaseException(2006) }
            try (text = NativeString(sql)) {
                let stmt = unsafe { zw_stmt_prepare(handle, text.value, UInt64(sql.toArray().size)) }
                try {
                    let error = unsafe { zw_stmt_error(stmt) }
                    if (error != 0) { throw DatabaseException(error) }
                    if (unsafe { zw_stmt_param_count(stmt) } != UInt64(params.size)) {
                        throw IllegalArgumentException("SQL 参数数量不匹配")
                    }
                    for (index in 0..params.size) {
                        let item = params[index] ?? ""
                        try (value = NativeString(item)) {
                            let result = unsafe { zw_stmt_bind(stmt, UInt64(index), value.value,
                                UInt64(item.toArray().size), if (params[index].isNone()) { 1 } else { 0 }) }
                            if (result != 0) { throw DatabaseException(unsafe { zw_stmt_error(stmt) }) }
                        }
                    }
                    if (unsafe { zw_stmt_execute(stmt) } != 0) {
                        throw DatabaseException(unsafe { zw_stmt_error(stmt) })
                    }
                    let rows = ArrayList<HashMap<String, Option<String>>>()
                    let columns = unsafe { zw_stmt_columns(stmt) }
                    while (true) {
                        let result = unsafe { zw_stmt_next(stmt) }
                        if (result == 0) { break }
                        if (result < 0) { throw DatabaseException(unsafe { zw_stmt_error(stmt) }) }
                        let row = HashMap<String, Option<String>>()
                        for (index in 0..columns) {
                            let key = unsafe { zw_stmt_column_name(stmt, index) }.toString()
                            if (unsafe { zw_stmt_value(stmt, index) }.isNull()) {
                                row[key] = None
                            } else {
                                let size = Int64(unsafe { zw_stmt_length(stmt, index) })
                                let bytes = Array<UInt8>(size, repeat: 0)
                                unsafe {
                                    let raw = acquireArrayRawData(bytes)
                                    try {
                                        if (zw_stmt_copy(stmt, index, raw.pointer, UInt64(size)) != 0) {
                                            throw DatabaseException(2032)
                                        }
                                    } finally { releaseArrayRawData(raw) }
                                }
                                row[key] = Some(String.fromUtf8(bytes))
                            }
                        }
                        rows.add(row)
                    }
                    return QueryResult(rows, unsafe { zw_stmt_affected(stmt) })
                } finally {
                    unsafe { zw_stmt_close(stmt) }
                }
            }
            throw DatabaseException(2000)
        }
    }

    private func controlTransaction(operation: Int32): Unit {
        if (closed) { throw DatabaseException(2006) }
        let code = unsafe { zw_mysql_transaction(handle, operation) }
        if (code != 0) { throw DatabaseException(code) }
    }

    public func transaction<T>(work: (Database) -> T): T {
        synchronized(mutex) {
            if (inTransaction) { throw IllegalArgumentException("不支持嵌套事务") }
            controlTransaction(0)
            inTransaction = true
            try {
                let result = work(this)
                controlTransaction(1)
                return result
            } catch (error: Exception) {
                try { controlTransaction(2) } catch (_: Exception) { close() }
                throw error
            } finally {
                inTransaction = false
            }
        }
    }
}
