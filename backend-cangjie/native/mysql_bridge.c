/* Thin MySQL C ABI adapter. SQL, transactions and business decisions live in Cangjie.
 * Never return mysql_error(): it may contain SQL values or credentials.
 */
#include <mysql.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static pthread_once_t library_once = PTHREAD_ONCE_INIT;
static void init_library(void) { mysql_library_init(0, NULL, NULL); }
static void enter_mysql(void) { pthread_once(&library_once, init_library); mysql_thread_init(); }

void *zw_mysql_open(const char *host, unsigned int port, const char *user,
                    const char *password, const char *database) {
    enter_mysql();
    MYSQL *db = mysql_init(NULL);
    unsigned int timeout = 10;
    if (db) {
        mysql_options(db, MYSQL_OPT_CONNECT_TIMEOUT, &timeout);
        mysql_options(db, MYSQL_OPT_READ_TIMEOUT, &timeout);
        mysql_options(db, MYSQL_OPT_WRITE_TIMEOUT, &timeout);
        mysql_options(db, MYSQL_SET_CHARSET_NAME, "utf8mb4");
        if (!mysql_real_connect(db, host, user, password, database, port, NULL, 0)) {
            mysql_close(db);
            db = NULL;
        }
    }
    mysql_thread_end();
    return db;
}

void zw_mysql_close(void *db) {
    enter_mysql();
    if (db) mysql_close(db);
    mysql_thread_end();
}

typedef struct {
    MYSQL_STMT *stmt;
    MYSQL_RES *metadata;
    MYSQL_BIND *params, *columns;
    char **values;
    unsigned long *lengths;
    bool *nulls;
    unsigned long param_count;
    unsigned int column_count;
    unsigned int error;
    uint64_t affected;
} ZwStatement;

void zw_stmt_close(void *handle) {
    if (!handle) return;
    ZwStatement *s = handle;
    enter_mysql();
    if (s->stmt) mysql_stmt_close(s->stmt);
    if (s->metadata) mysql_free_result(s->metadata);
    for (unsigned long i = 0; i < s->param_count; i++) free(s->params[i].buffer);
    for (unsigned int i = 0; i < s->column_count; i++) free(s->values ? s->values[i] : NULL);
    free(s->params); free(s->columns); free(s->values); free(s->lengths); free(s->nulls);
    free(s);
    mysql_thread_end();
}

void *zw_stmt_prepare(void *db, const char *sql, unsigned long length) {
    if (!db) return NULL;
    ZwStatement *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    enter_mysql();
    s->stmt = mysql_stmt_init(db);
    if (!s->stmt || mysql_stmt_prepare(s->stmt, sql, length)) {
        s->error = s->stmt ? mysql_stmt_errno(s->stmt) : 2008;
    } else {
        s->param_count = mysql_stmt_param_count(s->stmt);
        if (s->param_count) {
            s->params = calloc(s->param_count, sizeof(*s->params));
            if (!s->params) { s->param_count = 0; s->error = 2008; }
        }
    }
    mysql_thread_end();
    return s;
}

unsigned int zw_stmt_error(void *handle) { return handle ? ((ZwStatement *)handle)->error : 2008; }
unsigned long zw_stmt_param_count(void *handle) { return ((ZwStatement *)handle)->param_count; }

int zw_stmt_bind(void *handle, unsigned long index, const char *value, unsigned long length, int is_null) {
    ZwStatement *s = handle;
    if (!s || s->error || index >= s->param_count) return -1;
    MYSQL_BIND *binding = &s->params[index];
    free(binding->buffer);
    memset(binding, 0, sizeof(*binding));
    binding->buffer_type = is_null ? MYSQL_TYPE_NULL : MYSQL_TYPE_STRING;
    if (!is_null) {
        binding->buffer = malloc(length + 1);
        if (!binding->buffer) { s->error = 2008; return -1; }
        memcpy(binding->buffer, value, length);
        ((char *)binding->buffer)[length] = 0;
        binding->buffer_length = length;
    }
    return 0;
}

int zw_stmt_execute(void *handle) {
    ZwStatement *s = handle;
    if (!s || s->error) return -1;
    enter_mysql();
    bool update_lengths = true;
    if (mysql_stmt_attr_set(s->stmt, STMT_ATTR_UPDATE_MAX_LENGTH, &update_lengths) ||
        (s->param_count && mysql_stmt_bind_param(s->stmt, s->params)) || mysql_stmt_execute(s->stmt)) goto failure;
    s->affected = mysql_stmt_affected_rows(s->stmt);
    if (!mysql_stmt_field_count(s->stmt)) {
        mysql_thread_end();
        return 0;
    }
    if (mysql_stmt_store_result(s->stmt)) goto failure;
    s->metadata = mysql_stmt_result_metadata(s->stmt);
    if (!s->metadata) goto failure;
    s->column_count = mysql_num_fields(s->metadata);
    s->columns = calloc(s->column_count, sizeof(*s->columns));
    s->values = calloc(s->column_count, sizeof(*s->values));
    s->lengths = calloc(s->column_count, sizeof(*s->lengths));
    s->nulls = calloc(s->column_count, sizeof(*s->nulls));
    if (!s->columns || !s->values || !s->lengths || !s->nulls) { s->error = 2008; goto failure; }
    MYSQL_FIELD *fields = mysql_fetch_fields(s->metadata);
    for (unsigned int i = 0; i < s->column_count; i++) {
        if (fields[i].max_length > 16 * 1024 * 1024) { s->error = 2020; goto failure; }
        s->values[i] = calloc(fields[i].max_length + 1, 1);
        if (!s->values[i]) { s->error = 2008; goto failure; }
        s->columns[i].buffer_type = MYSQL_TYPE_STRING;
        s->columns[i].buffer = s->values[i];
        s->columns[i].buffer_length = fields[i].max_length;
        s->columns[i].length = &s->lengths[i];
        s->columns[i].is_null = &s->nulls[i];
    }
    if (mysql_stmt_bind_result(s->stmt, s->columns)) goto failure;
    mysql_thread_end();
    return 0;
failure:
    if (!s->error) s->error = mysql_stmt_errno(s->stmt);
    if (!s->error) s->error = 2000;
    mysql_thread_end();
    return -1;
}

int zw_stmt_next(void *handle) {
    ZwStatement *s = handle;
    if (!s || s->error || !s->metadata) return 0;
    enter_mysql();
    int code = mysql_stmt_fetch(s->stmt);
    if (code != 0 && code != MYSQL_NO_DATA) s->error = mysql_stmt_errno(s->stmt) ? mysql_stmt_errno(s->stmt) : 2032;
    mysql_thread_end();
    return code == MYSQL_NO_DATA ? 0 : code == 0 ? 1 : -1;
}
unsigned int zw_stmt_columns(void *handle) { return ((ZwStatement *)handle)->column_count; }
const char *zw_stmt_column_name(void *handle, unsigned int index) {
    ZwStatement *s = handle;
    return index < s->column_count ? mysql_fetch_fields(s->metadata)[index].name : NULL;
}
const char *zw_stmt_value(void *handle, unsigned int index) {
    ZwStatement *s = handle;
    if (index >= s->column_count || s->nulls[index]) return NULL;
    s->values[index][s->lengths[index]] = 0;
    return s->values[index];
}
unsigned long zw_stmt_length(void *handle, unsigned int index) {
    ZwStatement *s = handle;
    return index < s->column_count ? s->lengths[index] : 0;
}
uint64_t zw_stmt_affected(void *handle) { return ((ZwStatement *)handle)->affected; }
int zw_stmt_copy(void *handle, unsigned int index, unsigned char *output, unsigned long capacity) {
    ZwStatement *s = handle;
    if (!s || index >= s->column_count || s->nulls[index] || capacity != s->lengths[index]) return -1;
    if (capacity) memcpy(output, s->values[index], capacity);
    return 0;
}
unsigned int zw_mysql_transaction(void *handle, int operation) {
    MYSQL *db = handle;
    if (!db) return 2006;
    enter_mysql();
    int result;
    if (operation == 0) result = mysql_autocommit(db, false);
    else if (operation == 1) result = mysql_commit(db);
    else result = mysql_rollback(db);
    if (!result && operation != 0) result = mysql_autocommit(db, true);
    unsigned int error = result ? mysql_errno(db) : 0;
    mysql_thread_end();
    return error;
}
