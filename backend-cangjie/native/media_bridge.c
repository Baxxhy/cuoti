/* POSIX file primitives only. Routing, signatures and HTTP semantics live in Cangjie. */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>

int32_t zw_media_open(const char *root, const char *path) {
    if (!path || !*path || *path == '/') return -1;
    int fd = open(root, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return -1;
    char *copy = strdup(path);
    if (!copy) { close(fd); return -1; }
    char *part = copy;
    for (;;) {
        char *next = strchr(part, '/');
        if (next) *next = '\0';
        if (!*part || !strcmp(part, ".") || !strcmp(part, "..")) { close(fd); fd = -1; break; }
        int child = openat(fd, part, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK | (next ? O_DIRECTORY : 0));
        close(fd);
        fd = child;
        if (fd < 0 || !next) break;
        part = next + 1;
    }
    free(copy);
    if (fd >= 0) {
        struct stat info;
        if (fstat(fd, &info) || !S_ISREG(info.st_mode)) { close(fd); return -1; }
    }
    return fd;
}

int64_t zw_media_stat(int32_t fd, int32_t field) {
    struct stat info;
    if (fstat(fd, &info)) return -1;
    if (field == 0) return info.st_size;
    if (field == 1) return (int64_t)info.st_mtim.tv_sec * 1000000000 + info.st_mtim.tv_nsec;
    return (int64_t)info.st_ino;
}

int64_t zw_media_read(int32_t fd, unsigned char *output, uint64_t capacity, int64_t offset) {
    ssize_t result;
    do { result = pread(fd, output, capacity, offset); } while (result < 0 && errno == EINTR);
    return result;
}

void zw_media_close(int32_t fd) { close(fd); }

static int media_parent(const char *root, const char *path, int create, char **storage, char **leaf) {
    if (!path || !*path || *path == '/') return -1;
    if (create && mkdir(root, 0700) && errno != EEXIST) return -1;
    int fd = open(root, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return -1;
    *storage = strdup(path);
    if (!*storage) { close(fd); return -1; }
    char *part = *storage;
    for (;;) {
        char *next = strchr(part, '/');
        if (next) *next = '\0';
        if (!*part || !strcmp(part, ".") || !strcmp(part, "..")) { close(fd); return -1; }
        if (!next) { *leaf = part; return fd; }
        if (create && mkdirat(fd, part, 0700) && errno != EEXIST) { close(fd); return -1; }
        int child = openat(fd, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        close(fd);
        if (child < 0) return -1;
        fd = child;
        part = next + 1;
    }
}

int32_t zw_media_write(const char *root, const char *path, const unsigned char *data, uint64_t size) {
    char *storage = NULL, *leaf = NULL;
    int parent = media_parent(root, path, 1, &storage, &leaf);
    if (parent < 0) { free(storage); return -1; }
    int fd = openat(parent, leaf, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) { close(parent); free(storage); return -1; }
    uint64_t offset = 0;
    int failed = 0;
    while (offset < size) {
        ssize_t count = write(fd, data + offset, size - offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) { failed = 1; break; }
        offset += (uint64_t)count;
    }
    if (!failed && fsync(fd)) failed = 1;
    if (close(fd)) failed = 1;
    if (failed) unlinkat(parent, leaf, 0);
    close(parent);
    free(storage);
    return failed ? -1 : 0;
}

int32_t zw_media_remove(const char *root, const char *path) {
    char *storage = NULL, *leaf = NULL;
    int parent = media_parent(root, path, 0, &storage, &leaf);
    if (parent < 0) { free(storage); return -1; }
    int result = unlinkat(parent, leaf, 0);
    close(parent);
    free(storage);
    return result;
}
