#!/usr/bin/env python3

from __future__ import annotations

import concurrent.futures
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UYA_BASE_OUT = ROOT / "src" / "command" / "catalog_generated_base.uya"
UYA_WRAPPER_OUT = ROOT / "src" / "command" / "catalog_generated.uya"
DOC_OUT = ROOT / "docs" / "redis-uya-command-matrix.md"
INDEX_URL = "https://redis.io/docs/latest/commands/index.xml"
USER_AGENT = "redis-uya-command-catalog/1.0"
FETCH_WORKERS = 8
FETCH_RETRIES = 3
PART_SIZE = 12

CORE_GROUPS = {
    "string",
    "hash",
    "list",
    "set",
    "sorted-set",
    "generic",
    "server",
    "connection",
    "transactions",
    "pubsub",
    "scripting",
    "stream",
    "bitmap",
    "geo",
    "hyperloglog",
    "cluster",
    "sentinel",
    "acl",
}

TIER_A_GROUPS = {
    "bitmap",
    "connection",
    "generic",
    "geo",
    "hash",
    "hyperloglog",
    "list",
    "pubsub",
    "scripting",
    "server",
    "set",
    "sorted-set",
    "stream",
    "string",
    "transactions",
}

TIER_B_GROUPS = {
    "cluster",
    "sentinel",
}

TIER_C_GROUPS = {
    "bf",
    "cf",
    "cms",
    "json",
    "search",
    "suggestion",
    "tdigest",
    "timeseries",
    "topk",
    "vector_set",
}

ADVANCED_GROUP_TARGETS = {
    "bitmap": "v0.9.2",
    "geo": "v0.9.2",
    "hyperloglog": "v0.9.2",
    "json": "v0.9.2",
    "search": "v0.9.2",
    "timeseries": "v0.9.2",
    "vector_set": "v0.9.2",
    "bf": "v0.9.2",
    "cf": "v0.9.2",
    "cms": "v0.9.2",
    "topk": "v0.9.2",
    "tdigest": "v0.9.2",
    "suggestion": "v0.9.2",
}

OPS_TARGET_NAMES = {
    "acl",
    "latency",
    "memory",
    "module",
    "monitor",
    "slowlog",
}

FULL_NAMES = {
    "append",
    "auth",
    "bgrewriteaof",
    "bgsave",
    "bitcount",
    "bitfield",
    "bitfield_ro",
    "bitop",
    "bitpos",
    "client|help",
    "client|id",
    "client|getredir",
    "client|setinfo",
    "cluster|help",
    "command|count",
    "command|docs",
    "command|help",
    "command|info",
    "config|help",
    "config|resetstat",
    "dbsize",
    "decr",
    "decrby",
    "del",
    "discard",
    "dump",
    "echo",
    "exec",
    "exists",
    "expire",
    "expireat",
    "expiretime",
    "flushall",
    "flushdb",
    "get",
    "getbit",
    "getdel",
    "getex",
    "getrange",
    "getset",
    "hello",
    "hget",
    "hgetall",
    "hdel",
    "hexists",
    "hincrby",
    "hincrbyfloat",
    "hkeys",
    "hlen",
    "hmget",
    "hscan",
    "hset",
    "hsetnx",
    "hstrlen",
    "hvals",
    "incr",
    "incrby",
    "incrbyfloat",
    "keys",
    "lastsave",
    "lindex",
    "linsert",
    "llen",
    "lmove",
    "lmpop",
    "lpop",
    "lpos",
    "lpush",
    "lpushx",
    "lrange",
    "lrem",
    "lset",
    "ltrim",
    "mget",
    "move",
    "mset",
    "msetnx",
    "multi",
    "object|encoding",
    "object|freq",
    "object|help",
    "object|idletime",
    "object|refcount",
    "persist",
    "ping",
    "pexpire",
    "pexpireat",
    "pexpiretime",
    "psetex",
    "psync",
    "pttl",
    "publish",
    "pubsub|channels",
    "pubsub|help",
    "pubsub|numpat",
    "pubsub|numsub",
    "psubscribe",
    "punsubscribe",
    "quit",
    "randomkey",
    "reset",
    "rename",
    "renamenx",
    "replicaof",
    "restore",
    "role",
    "rpop",
    "rpoplpush",
    "rpush",
    "rpushx",
    "sadd",
    "save",
    "scan",
    "sdiff",
    "sdiffstore",
    "scard",
    "select",
    "set",
    "setbit",
    "setex",
    "setnx",
    "setrange",
    "sismember",
    "shutdown",
    "sinter",
    "sintercard",
    "sinterstore",
    "smove",
    "smismember",
    "smembers",
    "sort",
    "sort_ro",
    "spop",
    "srandmember",
    "srem",
    "sscan",
    "subscribe",
    "sunion",
    "sunionstore",
    "strlen",
    "time",
    "touch",
    "ttl",
    "type",
    "unlink",
    "unsubscribe",
    "unwatch",
    "wait",
    "watch",
    "zadd",
    "zcard",
    "zcount",
    "zincrby",
    "zmscore",
    "zpopmax",
    "zpopmin",
    "zrange",
    "zrangebyscore",
    "zrank",
    "zscore",
    "zrem",
    "zremrangebyrank",
    "zremrangebyscore",
    "zrevrangebyscore",
    "zrevrank",
    "zscan",
}

PARTIAL_NAMES = {
    "auth",
    "bgrewriteaof",
    "bgsave",
    "blpop",
    "brpop",
    "brpoplpush",
    "bzmpop",
    "bzpopmax",
    "bzpopmin",
    "client",
    "client|getname",
    "client|kill",
    "client|info",
    "client|list",
    "client|pause",
    "client|setname",
    "client|tracking",
    "client|trackinginfo",
    "client|unpause",
    "cluster",
    "cluster|info",
    "cluster|keyslot",
    "cluster|meet",
    "cluster|nodes",
    "cluster|setslot",
    "cluster|slots",
    "command",
    "command|getkeys",
    "command|getkeysandflags",
    "command|list",
    "command|docs",
    "config",
    "config|get",
    "config|rewrite",
    "config|set",
    "flushall",
    "flushdb",
    "hello",
    "info",
    "move",
    "object",
    "publish",
    "pubsub",
    "pubsub|shardchannels",
    "pubsub|shardnumsub",
    "psync",
    "quit",
    "replicaof",
    "restore",
    "save",
    "select",
    "sort",
    "subscribe",
    "unsubscribe",
    "wait",
    "pfadd",
    "pfcount",
    "pfmerge",
}

ALIAS_NAMES = {
    "hmset": "hset",
    "slaveof": "replicaof",
    "substr": "getrange",
}


@dataclass
class CommandEntry:
    title: str
    name: str
    group: str
    module_name: str
    arity: int
    flags: list[str]
    acl_categories: list[str]
    tips: list[str]
    key_specs_resp: list[Any]
    summary: str
    since: str
    complexity: str
    arguments_resp: list[Any]
    is_pattern: bool
    is_top_level: bool
    first_key: int = 0
    last_key: int = 0
    key_step: int = 0
    status: str = "deferred"
    target_version: str = ""
    subcommands: list[str] = field(default_factory=list)


def fetch_text(url: str) -> str:
    last_error: Exception | None = None
    for _ in range(FETCH_RETRIES):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
    raise RuntimeError(f"failed to fetch {url}: {last_error}") from last_error


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def command_name_to_runtime(title: str) -> str:
    return title.lower().replace(" ", "|")


def module_name_for(group: str, name: str) -> str:
    head = name.split("|", 1)[0]
    if "." in head:
        return head.split(".", 1)[0]
    if group in ADVANCED_GROUP_TARGETS and group not in {"bitmap", "geo", "hyperloglog"}:
        return group
    return ""


def iter_argument_nodes(args: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for arg in args:
        if not isinstance(arg, dict):
            continue
        out.append(arg)
        nested = arg.get("arguments")
        if isinstance(nested, list):
            out.extend(iter_argument_nodes(nested))
    return out


def argument_is_pattern(args: list[Any]) -> bool:
    for arg in iter_argument_nodes(args):
        if arg.get("type") == "pattern":
            return True
    return False


def transform_doc_argument(arg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in arg.items():
        if key == "arguments" and isinstance(value, list):
            out[key] = [transform_doc_argument(item) for item in value if isinstance(item, dict)]
            continue
        if value is False or value is None:
            continue
        if isinstance(value, bool):
            if value:
                out[key] = 1
            continue
        out[key] = value
    return out


def transform_key_spec(spec: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    flags: list[str] = []
    for key, value in spec.items():
        if key in {"begin_search", "find_keys"}:
            continue
        if isinstance(value, bool) and value:
            flags.append(key)
    if flags:
        out["flags"] = flags
    if "begin_search" in spec:
        out["begin_search"] = spec["begin_search"]
    if "find_keys" in spec:
        out["find_keys"] = spec["find_keys"]
    return out


def infer_flags(meta: dict[str, Any]) -> list[str]:
    explicit = meta.get("command_flags")
    if isinstance(explicit, list) and explicit:
        return [normalize_text(item) for item in explicit if normalize_text(item)]

    acl = [normalize_text(item) for item in (meta.get("acl_categories") or []) if normalize_text(item)]
    flags: list[str] = []
    if "@write" in acl:
        flags.append("write")
    elif "@read" in acl:
        flags.append("readonly")
    if "@fast" in acl:
        flags.append("fast")
    return flags


def infer_argument_min_tokens(arg: dict[str, Any]) -> int:
    arg_type = arg.get("type")
    if arg.get("optional") or arg.get("multiple"):
        return 0
    nested = arg.get("arguments")
    if arg_type == "oneof" and isinstance(nested, list):
        counts = [infer_argument_min_tokens(item) for item in nested if isinstance(item, dict)]
        if not counts:
            return 0
        prefix = 1 if isinstance(arg.get("token"), str) and arg["token"] else 0
        return prefix + min(counts)
    if arg_type == "block" and isinstance(nested, list):
        prefix = 1 if isinstance(arg.get("token"), str) and arg["token"] else 0
        return prefix + sum(infer_argument_min_tokens(item) for item in nested if isinstance(item, dict))
    return 1


def argument_is_variable(arg: dict[str, Any]) -> bool:
    if arg.get("optional") or arg.get("multiple"):
        return True
    arg_type = arg.get("type")
    if arg_type in {"oneof", "block"}:
        return True
    nested = arg.get("arguments")
    if isinstance(nested, list):
        for item in nested:
            if isinstance(item, dict) and argument_is_variable(item):
                return True
    return False


def infer_arity(meta: dict[str, Any]) -> int:
    explicit = meta.get("arity")
    if isinstance(explicit, int):
        return explicit
    arguments = meta.get("arguments")
    if not isinstance(arguments, list):
        return 0
    minimum = 1
    variable = False
    for argument in arguments:
        if not isinstance(argument, dict):
            continue
        minimum += infer_argument_min_tokens(argument)
        if argument_is_variable(argument):
            variable = True
    if variable:
        return -minimum
    return minimum


def infer_key_specs(meta: dict[str, Any], flags: list[str]) -> list[dict[str, Any]]:
    explicit = meta.get("key_specs")
    if isinstance(explicit, list) and explicit:
        return [transform_key_spec(item) for item in explicit if isinstance(item, dict)]

    arguments = meta.get("arguments")
    if not isinstance(arguments, list):
        return []

    has_key = False
    multiple_key = False
    for argument in iter_argument_nodes(arguments):
        if argument.get("type") != "key":
            continue
        has_key = True
        if argument.get("multiple"):
            multiple_key = True
            break
    if not has_key:
        return []

    spec: dict[str, Any] = {
        "begin_search": {"type": "index", "spec": {"index": 1}},
        "find_keys": {
            "type": "range",
            "spec": {
                "lastkey": -1 if multiple_key else 0,
                "keystep": 1,
                "limit": 0,
            },
        },
        "access": True,
    }
    readonly = "readonly" in flags and "write" not in flags
    if readonly:
        spec["RO"] = True
    else:
        spec["RW"] = True
        spec["update"] = True
    return [transform_key_spec(spec)]


def legacy_key_triplet(key_specs: list[dict[str, Any]]) -> tuple[int, int, int]:
    for key_spec in key_specs:
        begin_search = key_spec.get("begin_search")
        find_keys = key_spec.get("find_keys")
        if not isinstance(begin_search, dict) or not isinstance(find_keys, dict):
            continue
        if begin_search.get("type") != "index" or find_keys.get("type") != "range":
            continue
        begin_spec = begin_search.get("spec")
        find_spec = find_keys.get("spec")
        if not isinstance(begin_spec, dict) or not isinstance(find_spec, dict):
            continue
        first = int(begin_spec.get("index", 0))
        last = int(find_spec.get("lastkey", 0))
        step = int(find_spec.get("keystep", 0))
        return first, last, step
    return 0, 0, 0


def build_docs_fields(meta: dict[str, Any]) -> list[tuple[str, Any]]:
    fields: list[tuple[str, Any]] = []
    summary = normalize_text(meta.get("description"))
    since = normalize_text(meta.get("since"))
    group = normalize_text(meta.get("group"))
    complexity = normalize_text(meta.get("complexity"))
    arguments = meta.get("arguments")
    if summary:
        fields.append(("summary", summary))
    if since:
        fields.append(("since", since))
    if group:
        fields.append(("group", group))
    if complexity:
        fields.append(("complexity", complexity))
    if isinstance(arguments, list) and arguments:
        fields.append(("arguments", [transform_doc_argument(item) for item in arguments if isinstance(item, dict)]))
    return fields


def resp_bulk(value: str) -> bytes:
    data = value.encode("utf-8")
    return f"${len(data)}\r\n".encode("ascii") + data + b"\r\n"


def resp_simple(value: str) -> bytes:
    data = value.encode("utf-8")
    return b"+" + data + b"\r\n"


def resp_integer(value: int) -> bytes:
    return f":{value}\r\n".encode("ascii")


def resp_null(resp3: bool) -> bytes:
    if resp3:
        return b"_\r\n"
    return b"$-1\r\n"


def resp_array(items: list[bytes]) -> bytes:
    return f"*{len(items)}\r\n".encode("ascii") + b"".join(items)


def resp_set(items: list[bytes]) -> bytes:
    return f"~{len(items)}\r\n".encode("ascii") + b"".join(items)


def resp_map(items: list[tuple[bytes, bytes]]) -> bytes:
    body = bytearray()
    for key, value in items:
        body.extend(key)
        body.extend(value)
    return f"%{len(items)}\r\n".encode("ascii") + bytes(body)


def encode_resp2(value: Any) -> bytes:
    if isinstance(value, tuple) and value and value[0] == "simple":
        return resp_simple(value[1])
    if isinstance(value, tuple) and value and value[0] in {"array", "set"}:
        return resp_array([encode_resp2(item) for item in value[1]])
    if isinstance(value, str):
        return resp_bulk(value)
    if isinstance(value, int):
        return resp_integer(value)
    if isinstance(value, list):
        return resp_array([encode_resp2(item) for item in value])
    if isinstance(value, dict):
        items = []
        for key, item in value.items():
            items.append(resp_bulk(str(key)))
            items.append(encode_resp2(item))
        return resp_array(items)
    raise TypeError(f"unsupported RESP2 value: {type(value)!r}")


def encode_resp3(value: Any, *, set_like: bool = False) -> bytes:
    if isinstance(value, tuple) and value and value[0] == "simple":
        return resp_simple(value[1])
    if isinstance(value, tuple) and value and value[0] == "set":
        return resp_set([encode_resp3(item) for item in value[1]])
    if isinstance(value, tuple) and value and value[0] == "array":
        return resp_array([encode_resp3(item) for item in value[1]])
    if isinstance(value, str):
        return resp_bulk(value)
    if isinstance(value, int):
        return resp_integer(value)
    if isinstance(value, list):
        items = [encode_resp3(item) for item in value]
        if set_like:
            return resp_set(items)
        return resp_array(items)
    if isinstance(value, dict):
        items: list[tuple[bytes, bytes]] = []
        for key, item in value.items():
            items.append((resp_bulk(str(key)), encode_resp3(item)))
        return resp_map(items)
    raise TypeError(f"unsupported RESP3 value: {type(value)!r}")


def uya_string_literal(data: bytes) -> str:
    parts: list[str] = []
    for byte in data:
        if byte == 92:
            parts.append("\\\\")
        elif byte == 34:
            parts.append("\\\"")
        elif byte == 13:
            parts.append("\\r")
        elif byte == 10:
            parts.append("\\n")
        elif 32 <= byte <= 126:
            parts.append(chr(byte))
        else:
            parts.append(f"\\x{byte:02x}")
    escaped = "".join(parts)
    return f'&"{escaped}"[0: {len(data)}]'


def part_label(index: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    label = ""
    value = index
    while True:
        label = alphabet[value % 26] + label
        if value < 26:
            break
        value = (value // 26) - 1
    return label


def target_version_for(entry: CommandEntry, status: str) -> str:
    if status in {"full", "partial", "alias"}:
        return ""
    if status == "standalone-error":
        return "v1.1.0"
    if entry.group in ADVANCED_GROUP_TARGETS:
        return ADVANCED_GROUP_TARGETS[entry.group]
    if entry.name.split("|", 1)[0] in OPS_TARGET_NAMES:
        return "v0.9.3"
    if entry.group == "acl":
        return "v0.9.3"
    if entry.group in {"connection", "generic", "server", "transactions", "pubsub", "scripting", "stream"}:
        return "v0.9.1"
    if entry.group in {"string", "hash", "list", "set", "sorted-set"}:
        return "v0.9.1"
    return "v0.9.1"


def classify_status(entry: CommandEntry) -> tuple[str, str]:
    if entry.name in ALIAS_NAMES:
        return "alias", target_version_for(entry, "alias")
    if entry.name in PARTIAL_NAMES:
        return "partial", target_version_for(entry, "partial")
    if entry.name in FULL_NAMES:
        return "full", target_version_for(entry, "full")
    if entry.group in {"cluster", "sentinel"}:
        return "standalone-error", target_version_for(entry, "standalone-error")
    return "deferred", target_version_for(entry, "deferred")


def build_info_value(entry: CommandEntry, entries_by_name: dict[str, CommandEntry], *, resp3: bool) -> list[Any]:
    first_key, last_key, key_step = legacy_key_triplet([
        {"begin_search": spec.get("begin_search"), "find_keys": spec.get("find_keys")}
        for spec in entry.key_specs_resp
        if isinstance(spec, dict)
    ])
    subcommands = [build_info_value(entries_by_name[name], entries_by_name, resp3=resp3) for name in entry.subcommands]
    flags_value: Any = [("simple", flag) for flag in entry.flags]
    acl_value: Any = [("simple", category) for category in entry.acl_categories]
    tips_value: Any = [("simple", tip) for tip in entry.tips]
    key_specs_value: Any = entry.key_specs_resp
    subcommands_value: Any = subcommands
    if resp3:
        flags_value = ("set", flags_value)
        acl_value = ("set", acl_value)
        tips_value = ("set", tips_value)
        key_specs_value = ("set", key_specs_value)
        subcommands_value = ("set", subcommands)
    return [
        entry.name,
        entry.arity,
        flags_value,
        first_key,
        last_key,
        key_step,
        acl_value,
        tips_value,
        key_specs_value,
        subcommands_value,
    ]


def build_docs_value(entry: CommandEntry) -> dict[str, Any]:
    value: dict[str, Any] = {}
    if entry.summary:
        value["summary"] = entry.summary
    if entry.since:
        value["since"] = entry.since
    if entry.group:
        value["group"] = entry.group
    if entry.complexity:
        value["complexity"] = entry.complexity
    if entry.arguments_resp:
        value["arguments"] = entry.arguments_resp
    return value


def parse_entry(title: str, link: str) -> CommandEntry:
    markdown = fetch_text(link + "index.html.md")
    if "```json metadata" not in markdown:
        raise RuntimeError(f"missing metadata block for {link}")
    block = markdown.split("```json metadata", 1)[1].split("```", 1)[0]
    meta = json.loads(block)
    name = command_name_to_runtime(meta["title"])
    raw_arguments = meta.get("arguments")
    arguments_resp = []
    if isinstance(raw_arguments, list):
        arguments_resp = [transform_doc_argument(item) for item in raw_arguments if isinstance(item, dict)]
    group = normalize_text(meta.get("group"))
    flags = infer_flags(meta)
    entry = CommandEntry(
        title=meta["title"],
        name=name,
        group=group,
        module_name=module_name_for(group, name),
        arity=infer_arity(meta),
        flags=flags,
        acl_categories=[normalize_text(item) for item in (meta.get("acl_categories") or []) if normalize_text(item)],
        tips=[],
        key_specs_resp=infer_key_specs(meta, flags),
        summary=normalize_text(meta.get("description")),
        since=normalize_text(meta.get("since")),
        complexity=normalize_text(meta.get("complexity")),
        arguments_resp=arguments_resp,
        is_pattern=argument_is_pattern(raw_arguments if isinstance(raw_arguments, list) else []),
        is_top_level="|" not in name,
    )
    entry.first_key, entry.last_key, entry.key_step = legacy_key_triplet(entry.key_specs_resp)
    entry.status, entry.target_version = classify_status(entry)
    return entry


def collect_command_links() -> list[tuple[str, str]]:
    xml_text = fetch_text(INDEX_URL)
    root = ET.fromstring(xml_text)
    items: list[tuple[str, str]] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not link.startswith("https://redis.io/docs/latest/commands/"):
            continue
        slug = link.rstrip("/").split("/")[-1]
        if re.fullmatch(r"redis-\d+-\d+-commands", slug):
            continue
        items.append((title, link))
    return items


def build_catalog() -> list[CommandEntry]:
    links = collect_command_links()
    entries: list[CommandEntry] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
        future_map = {
            executor.submit(parse_entry, title, link): (title, link)
            for title, link in links
        }
        for future in concurrent.futures.as_completed(future_map):
            title, _ = future_map[future]
            entry = future.result()
            entries.append(entry)
            print(f"[catalog] fetched {title}", file=sys.stderr)
    order = {command_name_to_runtime(title): index for index, (title, _) in enumerate(links)}
    entries.sort(key=lambda item: order[item.name])
    entries_by_name = {entry.name: entry for entry in entries}
    subcommands: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        if "|" in entry.name:
            parent = entry.name.split("|", 1)[0]
            subcommands[parent].append(entry.name)
    for entry in entries:
        entry.subcommands = subcommands.get(entry.name, [])
    return entries


def status_enum_name(status: str) -> str:
    return {
        "full": "status_full",
        "partial": "status_partial",
        "standalone-error": "status_standalone_error",
        "alias": "status_alias",
        "deferred": "status_deferred",
    }[status]


def render_uya_base() -> str:
    lines: list[str] = []
    lines.append("// generated by scripts/generate_command_catalog.py; DO NOT EDIT.\n")
    lines.append("export enum CommandCatalogStatus {\n")
    lines.append("    status_full,\n")
    lines.append("    status_partial,\n")
    lines.append("    status_standalone_error,\n")
    lines.append("    status_alias,\n")
    lines.append("    status_deferred,\n")
    lines.append("}\n\n")
    lines.append("export struct CommandCatalogEntry {\n")
    lines.append("    name: &[byte],\n")
    lines.append("    group: &[byte],\n")
    lines.append("    module_name: &[byte],\n")
    lines.append("    acl_tags: &[byte],\n")
    lines.append("    flag_tags: &[byte],\n")
    lines.append("    status: CommandCatalogStatus,\n")
    lines.append("    target_version: &[byte],\n")
    lines.append("    summary: &[byte],\n")
    lines.append("    since: &[byte],\n")
    lines.append("    complexity: &[byte],\n")
    lines.append("    is_pattern: bool,\n")
    lines.append("    is_top_level: bool,\n")
    lines.append("    arity: i32,\n")
    lines.append("    first_key: i32,\n")
    lines.append("    last_key: i32,\n")
    lines.append("    key_step: i32,\n")
    lines.append("}\n\n")
    return "".join(lines)


def render_uya_part(entries: list[CommandEntry], part_index: int, start: int, end: int) -> str:
    label = part_label(part_index)
    lines: list[str] = []
    lines.append("// generated by scripts/generate_command_catalog.py; DO NOT EDIT.\n")
    lines.append("use src.command.catalog_generated_base.CommandCatalogEntry;\n")
    lines.append("use src.command.catalog_generated_base.CommandCatalogStatus;\n\n")
    lines.append(f"export fn command_catalog_generated_part_{label}(index: usize) CommandCatalogEntry {{\n")
    for index, entry in enumerate(entries):
        if index < start or index >= end:
            continue
        include_runtime_details = entry.status == "full"
        acl_tags = "|".join(category.lstrip("@").lower() for category in entry.acl_categories) if include_runtime_details else ""
        flag_tags = "|".join(flag.lower() for flag in entry.flags) if include_runtime_details else ""
        summary = entry.summary if include_runtime_details else ""
        since = entry.since if include_runtime_details else ""
        complexity = entry.complexity if include_runtime_details else ""
        lines.append(f"    if index == {index} {{\n")
        lines.append("        return CommandCatalogEntry{\n")
        lines.append(f"            name: {uya_string_literal(entry.name.encode('utf-8'))},\n")
        lines.append(f"            group: {uya_string_literal(entry.group.encode('utf-8'))},\n")
        lines.append(f"            module_name: {uya_string_literal(entry.module_name.encode('utf-8'))},\n")
        lines.append(f"            acl_tags: {uya_string_literal(acl_tags.encode('utf-8'))},\n")
        lines.append(f"            flag_tags: {uya_string_literal(flag_tags.encode('utf-8'))},\n")
        lines.append(f"            status: CommandCatalogStatus.{status_enum_name(entry.status)},\n")
        lines.append(f"            target_version: {uya_string_literal(entry.target_version.encode('utf-8'))},\n")
        lines.append(f"            summary: {uya_string_literal(summary.encode('utf-8'))},\n")
        lines.append(f"            since: {uya_string_literal(since.encode('utf-8'))},\n")
        lines.append(f"            complexity: {uya_string_literal(complexity.encode('utf-8'))},\n")
        lines.append(f"            is_pattern: {'true' if entry.is_pattern else 'false'},\n")
        lines.append(f"            is_top_level: {'true' if entry.is_top_level else 'false'},\n")
        lines.append(f"            arity: {entry.arity},\n")
        lines.append(f"            first_key: {entry.first_key},\n")
        lines.append(f"            last_key: {entry.last_key},\n")
        lines.append(f"            key_step: {entry.key_step},\n")
        lines.append("        };\n")
        lines.append("    }\n")
    lines.append("    return CommandCatalogEntry{\n")
    lines.append('        name: &""[0: 0],\n')
    lines.append('        group: &""[0: 0],\n')
    lines.append('        module_name: &""[0: 0],\n')
    lines.append('        acl_tags: &""[0: 0],\n')
    lines.append('        flag_tags: &""[0: 0],\n')
    lines.append("        status: CommandCatalogStatus.status_deferred,\n")
    lines.append('        target_version: &""[0: 0],\n')
    lines.append('        summary: &""[0: 0],\n')
    lines.append('        since: &""[0: 0],\n')
    lines.append('        complexity: &""[0: 0],\n')
    lines.append("        is_pattern: false,\n")
    lines.append("        is_top_level: false,\n")
    lines.append("        arity: 0,\n")
    lines.append("        first_key: 0,\n")
    lines.append("        last_key: 0,\n")
    lines.append("        key_step: 0,\n")
    lines.append("    };\n")
    lines.append("}\n")
    return "".join(lines)


def render_uya_wrapper(entries: list[CommandEntry]) -> str:
    total_count = len(entries)
    top_level_count = sum(1 for entry in entries if entry.is_top_level)
    part_count = (total_count + PART_SIZE - 1) // PART_SIZE
    lines: list[str] = []
    lines.append("// generated by scripts/generate_command_catalog.py; DO NOT EDIT.\n")
    lines.append("export error CommandUnknown;\n")
    lines.append("use src.command.catalog_generated_base.CommandCatalogEntry;\n")
    for part_index in range(part_count):
        label = part_label(part_index)
        lines.append(
            f"use src.command.catalog_generated_part_{label}.command_catalog_generated_part_{label};\n"
        )
    lines.append("\n")
    lines.append(f"export const COMMAND_CATALOG_TOTAL_COUNT: usize = {total_count};\n")
    lines.append(f"export const COMMAND_CATALOG_TOP_LEVEL_COUNT: usize = {top_level_count};\n\n")
    lines.append("export fn command_catalog_generated_entry(index: usize) !CommandCatalogEntry {\n")
    for part_index in range(part_count):
        start = part_index * PART_SIZE
        end = min(total_count, start + PART_SIZE)
        label = part_label(part_index)
        lines.append(f"    if index >= {start} && index < {end} {{\n")
        lines.append(f"        return command_catalog_generated_part_{label}(index);\n")
        lines.append("    }\n")
    lines.append("    return error.CommandUnknown;\n")
    lines.append("}\n")
    return "".join(lines)


def render_docs(entries: list[CommandEntry]) -> str:
    today = date.today().isoformat()
    total = len(entries)
    top_level = sum(1 for entry in entries if entry.is_top_level)
    status_counter = Counter(entry.status for entry in entries)
    group_counter = Counter(entry.group for entry in entries)
    tier_labels = {
        "tier-a-core": "Tier A: standalone core",
        "tier-b-mode": "Tier B: mode commands",
        "tier-c-module": "Tier C: module commands",
    }
    tier_order = ["tier-a-core", "tier-b-mode", "tier-c-module"]
    tier_entries: dict[str, list[CommandEntry]] = {tier: [] for tier in tier_order}
    for entry in entries:
        if entry.group in TIER_A_GROUPS:
            tier_entries["tier-a-core"].append(entry)
            continue
        if entry.group in TIER_B_GROUPS:
            tier_entries["tier-b-mode"].append(entry)
            continue
        if entry.group in TIER_C_GROUPS:
            tier_entries["tier-c-module"].append(entry)
            continue
        raise RuntimeError(f"unclassified command group for scope tier: {entry.group}")
    lines: list[str] = []
    lines.append("# redis-uya command matrix\n\n")
    lines.append("> version: v0.9.1-dev\n")
    lines.append(f"> date: {today}\n")
    lines.append("> source: Redis 8.6 Commands Reference + `scripts/generate_command_catalog.py`\n")
    lines.append("> runtime source: `src/command/catalog_generated.uya`\n\n")
    lines.append("## Summary\n\n")
    lines.append(f"- tracked official command names: `{total}`\n")
    lines.append(f"- tracked top-level command names: `{top_level}`\n")
    lines.append(f"- `COMMAND` / `COMMAND INFO` / `COMMAND DOCS` / `COMMAND LIST` / `COMMAND COUNT` share the same generated catalog\n")
    lines.append("- `v1.0.0` 完成度必须优先按 Tier A / Tier B / Tier C 分层阅读，不能再用总条目数代表当前单机完成度\n")
    lines.append("\n## Scope tier counts\n\n")
    lines.append("| tier | tracked official names | tracked top-level names | `full` | `partial` | `standalone-error` | `alias` | `deferred` |\n")
    lines.append("|------|-----------------------:|------------------------:|-------:|----------:|-------------------:|--------:|-----------:|\n")
    for tier in tier_order:
        scoped_entries = tier_entries[tier]
        scoped_statuses = Counter(entry.status for entry in scoped_entries)
        scoped_top_level = sum(1 for entry in scoped_entries if entry.is_top_level)
        lines.append(
            f"| {tier_labels[tier]} | "
            f"{len(scoped_entries)} | "
            f"{scoped_top_level} | "
            f"{scoped_statuses.get('full', 0)} | "
            f"{scoped_statuses.get('partial', 0)} | "
            f"{scoped_statuses.get('standalone-error', 0)} | "
            f"{scoped_statuses.get('alias', 0)} | "
            f"{scoped_statuses.get('deferred', 0)} |\n"
        )
    lines.append("\n## Status counts\n\n")
    lines.append("| status | count |\n")
    lines.append("|--------|-------|\n")
    for status in ["full", "partial", "standalone-error", "alias", "deferred"]:
        lines.append(f"| `{status}` | `{status_counter.get(status, 0)}` |\n")
    lines.append("\n## Group counts\n\n")
    lines.append("| group | count |\n")
    lines.append("|-------|-------|\n")
    for group, count in sorted(group_counter.items()):
        lines.append(f"| `{group}` | `{count}` |\n")
    lines.append("\n## Matrix\n\n")
    lines.append("| name | group | status | target | arity | module | pattern | acl |\n")
    lines.append("|------|-------|--------|--------|-------|--------|---------|-----|\n")
    for entry in entries:
        target = entry.target_version or "-"
        module = entry.module_name or "-"
        pattern = "yes" if entry.is_pattern else "no"
        acl = ", ".join(entry.acl_categories) if entry.acl_categories else "-"
        lines.append(
            f"| `{entry.name}` | `{entry.group}` | `{entry.status}` | `{target}` | `{entry.arity}` | `{module}` | `{pattern}` | `{acl}` |\n"
        )
    return "".join(lines)


def main() -> int:
    entries = build_catalog()
    UYA_BASE_OUT.write_text(render_uya_base(), encoding="utf-8")
    UYA_WRAPPER_OUT.write_text(render_uya_wrapper(entries), encoding="utf-8")
    part_count = (len(entries) + PART_SIZE - 1) // PART_SIZE
    for part_path in (ROOT / "src" / "command").glob("catalog_generated_part_*.uya"):
        part_path.unlink()
    for part_index in range(part_count):
        start = part_index * PART_SIZE
        end = min(len(entries), start + PART_SIZE)
        part_path = ROOT / "src" / "command" / f"catalog_generated_part_{part_label(part_index)}.uya"
        part_path.write_text(render_uya_part(entries, part_index, start, end), encoding="utf-8")
    DOC_OUT.write_text(render_docs(entries), encoding="utf-8")
    print(
        "wrote "
        f"{UYA_BASE_OUT.relative_to(ROOT)}, "
        f"{UYA_WRAPPER_OUT.relative_to(ROOT)}, "
        f"{part_count} part files and {DOC_OUT.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
