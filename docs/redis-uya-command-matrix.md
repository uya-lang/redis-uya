# redis-uya command matrix

> version: v0.9.1-dev
> date: 2026-06-20
> source: Redis 8.6 Commands Reference + `scripts/generate_command_catalog.py`
> runtime source: `src/command/catalog_generated.uya`

## Summary

- tracked official command names: `552`
- tracked top-level command names: `409`
- `COMMAND` / `COMMAND INFO` / `COMMAND DOCS` / `COMMAND LIST` / `COMMAND COUNT` share the same generated catalog
- `v1.0.0` 完成度必须优先按 Tier A / Tier B / Tier C 分层阅读，不能再用总条目数代表当前单机完成度

## Scope tier counts

| tier | tracked official names | tracked top-level names | `full` | `partial` | `standalone-error` | `alias` | `deferred` |
|------|-----------------------:|------------------------:|-------:|----------:|-------------------:|--------:|-----------:|
| Tier A: standalone core | 365 | 259 | 146 | 174 | 3 | 3 | 39 |
| Tier B: mode commands | 34 | 4 | 1 | 7 | 26 | 0 | 0 |
| Tier C: module commands | 153 | 146 | 0 | 0 | 0 | 0 | 153 |

## Status counts

| status | count |
|--------|-------|
| `full` | `147` |
| `partial` | `181` |
| `standalone-error` | `29` |
| `alias` | `3` |
| `deferred` | `192` |

## Group counts

| group | count |
|-------|-------|
| `array` | `18` |
| `bf` | `10` |
| `bitmap` | `7` |
| `cf` | `12` |
| `cluster` | `34` |
| `cms` | `6` |
| `connection` | `26` |
| `generic` | `34` |
| `geo` | `10` |
| `hash` | `28` |
| `hyperloglog` | `5` |
| `json` | `26` |
| `list` | `22` |
| `pubsub` | `15` |
| `scripting` | `23` |
| `search` | `26` |
| `server` | `82` |
| `set` | `17` |
| `sorted-set` | `35` |
| `stream` | `30` |
| `string` | `26` |
| `suggestion` | `4` |
| `tdigest` | `14` |
| `timeseries` | `17` |
| `topk` | `7` |
| `transactions` | `5` |
| `vector_set` | `13` |

## Matrix

| name | group | status | target | arity | module | pattern | acl |
|------|-------|--------|--------|-------|--------|---------|-----|
| `acl` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `acl|cat` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `acl|deluser` | `server` | `partial` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|dryrun` | `server` | `partial` | `-` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|genpass` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `acl|getuser` | `server` | `partial` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|help` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `acl|list` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|load` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|log` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|save` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|setuser` | `server` | `partial` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|users` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|whoami` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `append` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `arcount` | `array` | `deferred` | `v0.9.2` | `2` | `array` | `no` | `@read, @array, @fast` |
| `ardel` | `array` | `deferred` | `v0.9.2` | `-3` | `array` | `no` | `@write, @array, @fast` |
| `ardelrange` | `array` | `deferred` | `v0.9.2` | `-4` | `array` | `no` | `@write, @array, @slow` |
| `arget` | `array` | `deferred` | `v0.9.2` | `3` | `array` | `no` | `@read, @array, @fast` |
| `argetrange` | `array` | `deferred` | `v0.9.2` | `4` | `array` | `no` | `@read, @array, @slow` |
| `argrep` | `array` | `deferred` | `v0.9.2` | `-6` | `array` | `no` | `@read, @array, @slow` |
| `arinfo` | `array` | `deferred` | `v0.9.2` | `-2` | `array` | `no` | `@read, @array, @slow` |
| `arinsert` | `array` | `deferred` | `v0.9.2` | `-3` | `array` | `no` | `@write, @array, @fast` |
| `arlastitems` | `array` | `deferred` | `v0.9.2` | `-3` | `array` | `no` | `@read, @array, @slow` |
| `arlen` | `array` | `deferred` | `v0.9.2` | `2` | `array` | `no` | `@read, @array, @fast` |
| `armget` | `array` | `deferred` | `v0.9.2` | `-3` | `array` | `no` | `@read, @array, @fast` |
| `armset` | `array` | `deferred` | `v0.9.2` | `-4` | `array` | `no` | `@write, @array, @fast` |
| `arnext` | `array` | `deferred` | `v0.9.2` | `2` | `array` | `no` | `@read, @array, @fast` |
| `arop` | `array` | `deferred` | `v0.9.2` | `-5` | `array` | `no` | `@read, @array, @slow` |
| `arring` | `array` | `deferred` | `v0.9.2` | `-4` | `array` | `no` | `@write, @array, @slow` |
| `arscan` | `array` | `deferred` | `v0.9.2` | `-4` | `array` | `no` | `@read, @array, @slow` |
| `arseek` | `array` | `deferred` | `v0.9.2` | `3` | `array` | `no` | `@write, @array, @fast` |
| `arset` | `array` | `deferred` | `v0.9.2` | `-4` | `array` | `no` | `@write, @array, @fast` |
| `asking` | `cluster` | `standalone-error` | `v1.1.0` | `1` | `-` | `no` | `@fast, @connection` |
| `auth` | `connection` | `partial` | `-` | `-2` | `-` | `no` | `@fast, @connection` |
| `bf.add` | `bf` | `deferred` | `v0.9.2` | `3` | `bf` | `no` | `@bloom, @write, @slow` |
| `bf.card` | `bf` | `deferred` | `v0.9.2` | `2` | `bf` | `no` | `@bloom, @read, @fast` |
| `bf.exists` | `bf` | `deferred` | `v0.9.2` | `3` | `bf` | `no` | `@bloom, @read, @slow` |
| `bf.info` | `bf` | `deferred` | `v0.9.2` | `-2` | `bf` | `no` | `@bloom, @read, @fast` |
| `bf.insert` | `bf` | `deferred` | `v0.9.2` | `-3` | `bf` | `no` | `@bloom, @write, @slow` |
| `bf.loadchunk` | `bf` | `deferred` | `v0.9.2` | `4` | `bf` | `no` | `@bloom, @write, @slow` |
| `bf.madd` | `bf` | `deferred` | `v0.9.2` | `-2` | `bf` | `no` | `@bloom, @write, @slow` |
| `bf.mexists` | `bf` | `deferred` | `v0.9.2` | `-2` | `bf` | `no` | `@bloom, @read, @slow` |
| `bf.reserve` | `bf` | `deferred` | `v0.9.2` | `-4` | `bf` | `no` | `@bloom, @write, @fast` |
| `bf.scandump` | `bf` | `deferred` | `v0.9.2` | `3` | `bf` | `no` | `@bloom, @write, @slow` |
| `bgrewriteaof` | `server` | `partial` | `-` | `1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `bgsave` | `server` | `partial` | `-` | `-1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `bitcount` | `bitmap` | `full` | `-` | `-2` | `-` | `no` | `@read, @bitmap, @slow` |
| `bitfield` | `bitmap` | `full` | `-` | `-2` | `-` | `no` | `@write, @bitmap, @slow` |
| `bitfield_ro` | `bitmap` | `full` | `-` | `-2` | `-` | `no` | `@read, @bitmap, @fast` |
| `bitop` | `bitmap` | `full` | `-` | `-4` | `-` | `no` | `@write, @bitmap, @slow` |
| `bitpos` | `bitmap` | `full` | `-` | `-3` | `-` | `no` | `@read, @bitmap, @slow` |
| `blmove` | `list` | `partial` | `-` | `6` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `blmpop` | `list` | `partial` | `-` | `-5` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `blpop` | `list` | `partial` | `-` | `-3` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `brpop` | `list` | `partial` | `-` | `-3` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `brpoplpush` | `list` | `partial` | `-` | `4` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `bzmpop` | `sorted-set` | `partial` | `-` | `-5` | `-` | `no` | `@write, @sortedset, @slow, @blocking` |
| `bzpopmax` | `sorted-set` | `partial` | `-` | `-3` | `-` | `no` | `@write, @sortedset, @fast, @blocking` |
| `bzpopmin` | `sorted-set` | `partial` | `-` | `-3` | `-` | `no` | `@write, @sortedset, @fast, @blocking` |
| `cf.add` | `cf` | `deferred` | `v0.9.2` | `3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.addnx` | `cf` | `deferred` | `v0.9.2` | `3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.count` | `cf` | `deferred` | `v0.9.2` | `3` | `cf` | `no` | `@cuckoo, @read, @slow` |
| `cf.del` | `cf` | `deferred` | `v0.9.2` | `3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.exists` | `cf` | `deferred` | `v0.9.2` | `3` | `cf` | `no` | `@cuckoo, @read, @slow` |
| `cf.info` | `cf` | `deferred` | `v0.9.2` | `2` | `cf` | `no` | `@cuckoo, @read, @fast` |
| `cf.insert` | `cf` | `deferred` | `v0.9.2` | `-3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.insertnx` | `cf` | `deferred` | `v0.9.2` | `-3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.loadchunk` | `cf` | `deferred` | `v0.9.2` | `4` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.mexists` | `cf` | `deferred` | `v0.9.2` | `-2` | `cf` | `no` | `@cuckoo, @read, @slow` |
| `cf.reserve` | `cf` | `deferred` | `v0.9.2` | `-3` | `cf` | `no` | `@cuckoo, @write, @fast` |
| `cf.scandump` | `cf` | `deferred` | `v0.9.2` | `3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `client` | `connection` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `client|caching` | `connection` | `partial` | `-` | `3` | `-` | `no` | `@slow, @connection` |
| `client|getname` | `connection` | `partial` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|getredir` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|help` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|id` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|info` | `connection` | `partial` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|kill` | `connection` | `partial` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|list` | `connection` | `partial` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|no-evict` | `connection` | `partial` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|no-touch` | `connection` | `partial` | `-` | `3` | `-` | `no` | `@slow, @connection` |
| `client|pause` | `connection` | `partial` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|reply` | `connection` | `partial` | `-` | `3` | `-` | `no` | `@slow, @connection` |
| `client|setinfo` | `connection` | `full` | `-` | `4` | `-` | `no` | `@slow, @connection` |
| `client|setname` | `connection` | `partial` | `-` | `3` | `-` | `no` | `@slow, @connection` |
| `client|tracking` | `connection` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @connection` |
| `client|trackinginfo` | `connection` | `partial` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|unblock` | `connection` | `partial` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|unpause` | `connection` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `cluster` | `cluster` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `cluster|addslots` | `cluster` | `standalone-error` | `v1.1.0` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|addslotsrange` | `cluster` | `standalone-error` | `v1.1.0` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|bumpepoch` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|count-failure-reports` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|countkeysinslot` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@slow` |
| `cluster|delslots` | `cluster` | `standalone-error` | `v1.1.0` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|delslotsrange` | `cluster` | `standalone-error` | `v1.1.0` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|failover` | `cluster` | `standalone-error` | `v1.1.0` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|flushslots` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|forget` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|getkeysinslot` | `cluster` | `standalone-error` | `v1.1.0` | `4` | `-` | `no` | `@slow` |
| `cluster|help` | `cluster` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `cluster|info` | `cluster` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `cluster|keyslot` | `cluster` | `partial` | `-` | `3` | `-` | `no` | `@slow` |
| `cluster|links` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|meet` | `cluster` | `partial` | `-` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|migration` | `cluster` | `standalone-error` | `v1.1.0` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|myid` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|myshardid` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|nodes` | `cluster` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `cluster|replicas` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|replicate` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|reset` | `cluster` | `standalone-error` | `v1.1.0` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|saveconfig` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|set-config-epoch` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|setslot` | `cluster` | `partial` | `-` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|shards` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|slaves` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|slot-stats` | `cluster` | `standalone-error` | `v1.1.0` | `-4` | `-` | `no` | `-` |
| `cluster|slots` | `cluster` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `cms.incrby` | `cms` | `deferred` | `v0.9.2` | `-2` | `cms` | `no` | `@cms, @write` |
| `cms.info` | `cms` | `deferred` | `v0.9.2` | `2` | `cms` | `no` | `@cms, @read, @fast` |
| `cms.initbydim` | `cms` | `deferred` | `v0.9.2` | `4` | `cms` | `no` | `@cms, @write, @fast` |
| `cms.initbyprob` | `cms` | `deferred` | `v0.9.2` | `4` | `cms` | `no` | `@cms, @write, @fast` |
| `cms.merge` | `cms` | `deferred` | `v0.9.2` | `-3` | `cms` | `no` | `@cms, @write` |
| `cms.query` | `cms` | `deferred` | `v0.9.2` | `-2` | `cms` | `no` | `@cms, @read` |
| `command` | `server` | `partial` | `-` | `-1` | `-` | `no` | `@slow, @connection` |
| `command|count` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `command|docs` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow, @connection` |
| `command|getkeys` | `server` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @connection` |
| `command|getkeysandflags` | `server` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @connection` |
| `command|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `command|info` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow, @connection` |
| `command|list` | `server` | `partial` | `-` | `-2` | `-` | `yes` | `@slow, @connection` |
| `config` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `config|get` | `server` | `partial` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `config|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `config|resetstat` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `config|rewrite` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `config|set` | `server` | `partial` | `-` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `copy` | `generic` | `partial` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @slow` |
| `dbsize` | `server` | `full` | `-` | `1` | `-` | `no` | `@keyspace, @read, @fast` |
| `debug` | `server` | `standalone-error` | `v1.1.0` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `decr` | `string` | `full` | `-` | `2` | `-` | `no` | `@write, @string, @fast` |
| `decrby` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `del` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@keyspace, @write, @slow` |
| `delex` | `string` | `partial` | `-` | `-2` | `-` | `no` | `@write, @string, @fast` |
| `digest` | `string` | `deferred` | `v0.9.1` | `2` | `-` | `no` | `@read, @string, @fast` |
| `discard` | `transactions` | `full` | `-` | `1` | `-` | `no` | `@fast, @transaction` |
| `dump` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @slow` |
| `echo` | `connection` | `full` | `-` | `2` | `-` | `no` | `@fast, @connection` |
| `eval` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `eval_ro` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `evalsha` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `evalsha_ro` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `exec` | `transactions` | `full` | `-` | `1` | `-` | `no` | `@slow, @transaction` |
| `exists` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@keyspace, @read, @fast` |
| `expire` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @fast` |
| `expireat` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @fast` |
| `expiretime` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `failover` | `server` | `standalone-error` | `v1.1.0` | `-1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `fcall` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `fcall_ro` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `flushall` | `server` | `partial` | `-` | `-1` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `flushdb` | `server` | `partial` | `-` | `-1` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `ft._list` | `search` | `deferred` | `v0.9.2` | `0` | `ft` | `no` | `@admin, @search, @slow` |
| `ft.aggregate` | `search` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@search, @read, @fast` |
| `ft.aliasadd` | `search` | `deferred` | `v0.9.2` | `3` | `ft` | `no` | `@search` |
| `ft.aliasdel` | `search` | `deferred` | `v0.9.2` | `2` | `ft` | `no` | `@search` |
| `ft.aliasupdate` | `search` | `deferred` | `v0.9.2` | `3` | `ft` | `no` | `@search` |
| `ft.alter` | `search` | `deferred` | `v0.9.2` | `-6` | `ft` | `no` | `@search` |
| `ft.config|get` | `search` | `deferred` | `v0.9.2` | `2` | `ft` | `no` | `@admin, @search` |
| `ft.config|help` | `search` | `deferred` | `v0.9.2` | `2` | `ft` | `no` | `@admin, @search` |
| `ft.config|set` | `search` | `deferred` | `v0.9.2` | `3` | `ft` | `no` | `@admin, @search` |
| `ft.create` | `search` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@search` |
| `ft.cursor|del` | `search` | `deferred` | `v0.9.2` | `3` | `ft` | `no` | `@read, @search` |
| `ft.cursor|read` | `search` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@read, @search` |
| `ft.dictadd` | `search` | `deferred` | `v0.9.2` | `-2` | `ft` | `no` | `@search` |
| `ft.dictdel` | `search` | `deferred` | `v0.9.2` | `-2` | `ft` | `no` | `@search` |
| `ft.dictdump` | `search` | `deferred` | `v0.9.2` | `2` | `ft` | `no` | `@search` |
| `ft.dropindex` | `search` | `deferred` | `v0.9.2` | `-2` | `ft` | `no` | `@dangerous, @search, @slow, @write` |
| `ft.explain` | `search` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@search` |
| `ft.explaincli` | `search` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@search` |
| `ft.hybrid` | `search` | `deferred` | `v0.9.2` | `-7` | `ft` | `no` | `@read, @search` |
| `ft.info` | `search` | `deferred` | `v0.9.2` | `2` | `ft` | `no` | `@search` |
| `ft.profile` | `search` | `deferred` | `v0.9.2` | `-5` | `ft` | `no` | `@read, @search` |
| `ft.search` | `search` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@read, @search` |
| `ft.spellcheck` | `search` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@search` |
| `ft.sugadd` | `suggestion` | `deferred` | `v0.9.2` | `-4` | `ft` | `no` | `@search, @write` |
| `ft.sugdel` | `suggestion` | `deferred` | `v0.9.2` | `3` | `ft` | `no` | `@search, @write` |
| `ft.sugget` | `suggestion` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@search` |
| `ft.suglen` | `suggestion` | `deferred` | `v0.9.2` | `2` | `ft` | `no` | `@search` |
| `ft.syndump` | `search` | `deferred` | `v0.9.2` | `2` | `ft` | `no` | `@search` |
| `ft.synupdate` | `search` | `deferred` | `v0.9.2` | `-3` | `ft` | `no` | `@search` |
| `ft.tagvals` | `search` | `deferred` | `v0.9.2` | `3` | `ft` | `no` | `@dangerous, @read, @search, @slow` |
| `function` | `scripting` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `function|delete` | `scripting` | `partial` | `-` | `3` | `-` | `no` | `@write, @slow, @scripting` |
| `function|dump` | `scripting` | `partial` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `function|flush` | `scripting` | `partial` | `-` | `-2` | `-` | `no` | `@write, @slow, @scripting` |
| `function|help` | `scripting` | `partial` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `function|kill` | `scripting` | `partial` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `function|list` | `scripting` | `partial` | `-` | `-2` | `-` | `no` | `@slow, @scripting` |
| `function|load` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@write, @slow, @scripting` |
| `function|restore` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@write, @slow, @scripting` |
| `function|stats` | `scripting` | `partial` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `geoadd` | `geo` | `partial` | `-` | `-5` | `-` | `no` | `@write, @geo, @slow` |
| `geodist` | `geo` | `partial` | `-` | `-4` | `-` | `no` | `@read, @geo, @slow` |
| `geohash` | `geo` | `partial` | `-` | `-2` | `-` | `no` | `@read, @geo, @slow` |
| `geopos` | `geo` | `partial` | `-` | `-2` | `-` | `no` | `@read, @geo, @slow` |
| `georadius` | `geo` | `partial` | `-` | `-6` | `-` | `no` | `@write, @geo, @slow` |
| `georadius_ro` | `geo` | `partial` | `-` | `-6` | `-` | `no` | `@read, @geo, @slow` |
| `georadiusbymember` | `geo` | `partial` | `-` | `-5` | `-` | `no` | `@write, @geo, @slow` |
| `georadiusbymember_ro` | `geo` | `partial` | `-` | `-5` | `-` | `no` | `@read, @geo, @slow` |
| `geosearch` | `geo` | `partial` | `-` | `-7` | `-` | `no` | `@read, @geo, @slow` |
| `geosearchstore` | `geo` | `partial` | `-` | `-8` | `-` | `no` | `@write, @geo, @slow` |
| `get` | `string` | `full` | `-` | `2` | `-` | `no` | `@read, @string, @fast` |
| `getbit` | `bitmap` | `full` | `-` | `3` | `-` | `no` | `@read, @bitmap, @fast` |
| `getdel` | `string` | `full` | `-` | `2` | `-` | `no` | `@write, @string, @fast` |
| `getex` | `string` | `full` | `-` | `-2` | `-` | `no` | `@write, @string, @fast` |
| `getrange` | `string` | `full` | `-` | `4` | `-` | `no` | `@read, @string, @slow` |
| `getset` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `hdel` | `hash` | `full` | `-` | `-3` | `-` | `no` | `@write, @hash, @fast` |
| `hello` | `connection` | `partial` | `-` | `-1` | `-` | `no` | `@fast, @connection` |
| `hexists` | `hash` | `full` | `-` | `3` | `-` | `no` | `@read, @hash, @fast` |
| `hexpire` | `hash` | `deferred` | `v0.9.1` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hexpireat` | `hash` | `deferred` | `v0.9.1` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hexpiretime` | `hash` | `deferred` | `v0.9.1` | `-5` | `-` | `no` | `@read, @hash, @fast` |
| `hget` | `hash` | `full` | `-` | `3` | `-` | `no` | `@read, @hash, @fast` |
| `hgetall` | `hash` | `full` | `-` | `2` | `-` | `no` | `@read, @hash, @slow` |
| `hgetdel` | `hash` | `deferred` | `v0.9.1` | `-5` | `-` | `no` | `@write, @hash, @fast` |
| `hgetex` | `hash` | `deferred` | `v0.9.1` | `-5` | `-` | `no` | `@write, @hash, @fast` |
| `hincrby` | `hash` | `full` | `-` | `4` | `-` | `no` | `@write, @hash, @fast` |
| `hincrbyfloat` | `hash` | `full` | `-` | `4` | `-` | `no` | `@write, @hash, @fast` |
| `hkeys` | `hash` | `full` | `-` | `2` | `-` | `no` | `@read, @hash, @slow` |
| `hlen` | `hash` | `full` | `-` | `2` | `-` | `no` | `@read, @hash, @fast` |
| `hmget` | `hash` | `full` | `-` | `-3` | `-` | `no` | `@read, @hash, @fast` |
| `hmset` | `hash` | `alias` | `-` | `-4` | `-` | `no` | `@write, @hash, @fast` |
| `hotkeys` | `server` | `deferred` | `v0.9.1` | `-2` | `-` | `no` | `@slow` |
| `hotkeys|get` | `server` | `deferred` | `v0.9.1` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `hotkeys|help` | `server` | `deferred` | `v0.9.1` | `2` | `-` | `no` | `@admin` |
| `hotkeys|reset` | `server` | `deferred` | `v0.9.1` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `hotkeys|start` | `server` | `deferred` | `v0.9.1` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `hotkeys|stop` | `server` | `deferred` | `v0.9.1` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `hpersist` | `hash` | `deferred` | `v0.9.1` | `-5` | `-` | `no` | `@write, @hash, @fast` |
| `hpexpire` | `hash` | `deferred` | `v0.9.1` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hpexpireat` | `hash` | `deferred` | `v0.9.1` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hpexpiretime` | `hash` | `deferred` | `v0.9.1` | `-5` | `-` | `no` | `@read, @hash, @fast` |
| `hpttl` | `hash` | `deferred` | `v0.9.1` | `-5` | `-` | `no` | `@read, @hash, @fast` |
| `hrandfield` | `hash` | `partial` | `-` | `-2` | `-` | `no` | `@read, @hash, @slow` |
| `hscan` | `hash` | `full` | `-` | `-3` | `-` | `yes` | `@read, @hash, @slow` |
| `hset` | `hash` | `full` | `-` | `-4` | `-` | `no` | `@write, @hash, @fast` |
| `hsetex` | `hash` | `deferred` | `v0.9.1` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hsetnx` | `hash` | `full` | `-` | `4` | `-` | `no` | `@write, @hash, @fast` |
| `hstrlen` | `hash` | `full` | `-` | `3` | `-` | `no` | `@read, @hash, @fast` |
| `httl` | `hash` | `deferred` | `v0.9.1` | `-5` | `-` | `no` | `@read, @hash, @fast` |
| `hvals` | `hash` | `full` | `-` | `2` | `-` | `no` | `@read, @hash, @slow` |
| `incr` | `string` | `full` | `-` | `2` | `-` | `no` | `@write, @string, @fast` |
| `incrby` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `incrbyfloat` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `increx` | `string` | `deferred` | `v0.9.1` | `-2` | `-` | `no` | `@fast, @string, @write` |
| `info` | `server` | `partial` | `-` | `-1` | `-` | `no` | `@slow, @dangerous` |
| `json.arrappend` | `json` | `deferred` | `v0.9.2` | `-3` | `json` | `no` | `@json, @write, @slow` |
| `json.arrindex` | `json` | `deferred` | `v0.9.2` | `-4` | `json` | `no` | `@json, @read, @slow` |
| `json.arrinsert` | `json` | `deferred` | `v0.9.2` | `-4` | `json` | `no` | `@json, @write, @slow` |
| `json.arrlen` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.arrpop` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @write, @slow` |
| `json.arrtrim` | `json` | `deferred` | `v0.9.2` | `5` | `json` | `no` | `@json, @write, @slow` |
| `json.clear` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @write, @slow` |
| `json.debug` | `json` | `deferred` | `v0.9.2` | `0` | `json` | `no` | `-` |
| `json.debug|help` | `json` | `deferred` | `v0.9.2` | `0` | `json` | `no` | `-` |
| `json.debug|memory` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read` |
| `json.del` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @write, @slow` |
| `json.forget` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @write, @slow` |
| `json.get` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.merge` | `json` | `deferred` | `v0.9.2` | `4` | `json` | `no` | `@json, @write, @slow` |
| `json.mget` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.mset` | `json` | `deferred` | `v0.9.2` | `-1` | `json` | `no` | `@json, @write, @slow` |
| `json.numincrby` | `json` | `deferred` | `v0.9.2` | `4` | `json` | `no` | `@json, @write, @slow` |
| `json.nummultby` | `json` | `deferred` | `v0.9.2` | `4` | `json` | `no` | `@json, @write, @slow` |
| `json.objkeys` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.objlen` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.resp` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.set` | `json` | `deferred` | `v0.9.2` | `-4` | `json` | `no` | `@json, @write, @slow` |
| `json.strappend` | `json` | `deferred` | `v0.9.2` | `-3` | `json` | `no` | `@json, @write, @slow` |
| `json.strlen` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.toggle` | `json` | `deferred` | `v0.9.2` | `3` | `json` | `no` | `@json, @write, @slow` |
| `json.type` | `json` | `deferred` | `v0.9.2` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `keys` | `generic` | `full` | `-` | `2` | `-` | `yes` | `@keyspace, @read, @slow, @dangerous` |
| `lastsave` | `server` | `full` | `-` | `1` | `-` | `no` | `@admin, @fast, @dangerous` |
| `latency` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `latency|doctor` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|graph` | `server` | `partial` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|help` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `latency|histogram` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|history` | `server` | `partial` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|latest` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|reset` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `lcs` | `string` | `deferred` | `v0.9.1` | `-3` | `-` | `no` | `@read, @string, @slow` |
| `lindex` | `list` | `full` | `-` | `3` | `-` | `no` | `@read, @list, @slow` |
| `linsert` | `list` | `full` | `-` | `5` | `-` | `no` | `@write, @list, @slow` |
| `llen` | `list` | `full` | `-` | `2` | `-` | `no` | `@read, @list, @fast` |
| `lmove` | `list` | `full` | `-` | `5` | `-` | `no` | `@write, @list, @slow` |
| `lmpop` | `list` | `full` | `-` | `-4` | `-` | `no` | `@write, @list, @slow` |
| `lolwut` | `server` | `partial` | `-` | `-1` | `-` | `no` | `@read, @fast` |
| `lpop` | `list` | `full` | `-` | `-2` | `-` | `no` | `@write, @list, @fast` |
| `lpos` | `list` | `full` | `-` | `-3` | `-` | `no` | `@read, @list, @slow` |
| `lpush` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @fast` |
| `lpushx` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @fast` |
| `lrange` | `list` | `full` | `-` | `4` | `-` | `no` | `@read, @list, @slow` |
| `lrem` | `list` | `full` | `-` | `4` | `-` | `no` | `@write, @list, @slow` |
| `lset` | `list` | `full` | `-` | `4` | `-` | `no` | `@write, @list, @slow` |
| `ltrim` | `list` | `full` | `-` | `4` | `-` | `no` | `@write, @list, @slow` |
| `memory` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `memory|doctor` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|help` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|malloc-stats` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|purge` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|stats` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|usage` | `server` | `partial` | `-` | `-3` | `-` | `no` | `@read, @slow` |
| `mget` | `string` | `full` | `-` | `-2` | `-` | `no` | `@read, @string, @fast` |
| `migrate` | `generic` | `deferred` | `v0.9.1` | `-6` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `module` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `module|help` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `module|list` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `module|load` | `server` | `deferred` | `v0.9.3` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `module|loadex` | `server` | `deferred` | `v0.9.3` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `module|unload` | `server` | `deferred` | `v0.9.3` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `monitor` | `server` | `partial` | `-` | `1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `move` | `generic` | `partial` | `-` | `3` | `-` | `no` | `@keyspace, @write, @fast` |
| `mset` | `string` | `full` | `-` | `-3` | `-` | `no` | `@write, @string, @slow` |
| `msetex` | `string` | `deferred` | `v0.9.1` | `-4` | `-` | `no` | `@write, @string, @slow` |
| `msetnx` | `string` | `full` | `-` | `-3` | `-` | `no` | `@write, @string, @slow` |
| `multi` | `transactions` | `full` | `-` | `1` | `-` | `no` | `@fast, @transaction` |
| `object` | `generic` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `object|encoding` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @read, @slow` |
| `object|freq` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @read, @slow` |
| `object|help` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @slow` |
| `object|idletime` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @read, @slow` |
| `object|refcount` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @read, @slow` |
| `persist` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @write, @fast` |
| `pexpire` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @fast` |
| `pexpireat` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @fast` |
| `pexpiretime` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `pfadd` | `hyperloglog` | `partial` | `-` | `-2` | `-` | `no` | `@write, @hyperloglog, @fast` |
| `pfcount` | `hyperloglog` | `partial` | `-` | `-2` | `-` | `no` | `@read, @hyperloglog, @slow` |
| `pfdebug` | `hyperloglog` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@write, @hyperloglog, @admin, @slow, @dangerous` |
| `pfmerge` | `hyperloglog` | `partial` | `-` | `-2` | `-` | `no` | `@write, @hyperloglog, @slow` |
| `pfselftest` | `hyperloglog` | `partial` | `-` | `1` | `-` | `no` | `@hyperloglog, @admin, @slow, @dangerous` |
| `ping` | `connection` | `full` | `-` | `-1` | `-` | `no` | `@fast, @connection` |
| `psetex` | `string` | `full` | `-` | `4` | `-` | `no` | `@write, @string, @slow` |
| `psubscribe` | `pubsub` | `full` | `-` | `-2` | `-` | `yes` | `@pubsub, @slow` |
| `psync` | `server` | `partial` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `pttl` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `publish` | `pubsub` | `partial` | `-` | `3` | `-` | `no` | `@pubsub, @fast` |
| `pubsub` | `pubsub` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `pubsub|channels` | `pubsub` | `full` | `-` | `-2` | `-` | `yes` | `@pubsub, @slow` |
| `pubsub|help` | `pubsub` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `pubsub|numpat` | `pubsub` | `full` | `-` | `2` | `-` | `no` | `@pubsub, @slow` |
| `pubsub|numsub` | `pubsub` | `full` | `-` | `-2` | `-` | `no` | `@pubsub, @slow` |
| `pubsub|shardchannels` | `pubsub` | `partial` | `-` | `-2` | `-` | `yes` | `@pubsub, @slow` |
| `pubsub|shardnumsub` | `pubsub` | `partial` | `-` | `-2` | `-` | `no` | `@pubsub, @slow` |
| `punsubscribe` | `pubsub` | `full` | `-` | `-1` | `-` | `yes` | `@pubsub, @slow` |
| `quit` | `connection` | `partial` | `-` | `-1` | `-` | `no` | `@fast, @connection` |
| `randomkey` | `generic` | `full` | `-` | `1` | `-` | `no` | `@keyspace, @read, @slow` |
| `readonly` | `cluster` | `standalone-error` | `v1.1.0` | `1` | `-` | `no` | `@fast, @connection` |
| `readwrite` | `cluster` | `standalone-error` | `v1.1.0` | `1` | `-` | `no` | `@fast, @connection` |
| `rename` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @write, @slow` |
| `renamenx` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @write, @fast` |
| `replconf` | `server` | `partial` | `-` | `-1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `replicaof` | `server` | `partial` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `reset` | `connection` | `full` | `-` | `1` | `-` | `no` | `@fast, @connection` |
| `restore` | `generic` | `partial` | `-` | `-4` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `restore-asking` | `server` | `partial` | `-` | `-4` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `role` | `server` | `full` | `-` | `1` | `-` | `no` | `@admin, @fast, @dangerous` |
| `rpop` | `list` | `full` | `-` | `-2` | `-` | `no` | `@write, @list, @fast` |
| `rpoplpush` | `list` | `full` | `-` | `3` | `-` | `no` | `@write, @list, @slow` |
| `rpush` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @fast` |
| `rpushx` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @fast` |
| `sadd` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @fast` |
| `save` | `server` | `partial` | `-` | `1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `scan` | `generic` | `full` | `-` | `-2` | `-` | `yes` | `@keyspace, @read, @slow` |
| `scard` | `set` | `full` | `-` | `2` | `-` | `no` | `@read, @set, @fast` |
| `script` | `scripting` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `script|debug` | `scripting` | `partial` | `-` | `3` | `-` | `no` | `@slow, @scripting` |
| `script|exists` | `scripting` | `partial` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `script|flush` | `scripting` | `partial` | `-` | `-2` | `-` | `no` | `@slow, @scripting` |
| `script|help` | `scripting` | `partial` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `script|kill` | `scripting` | `partial` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `script|load` | `scripting` | `partial` | `-` | `3` | `-` | `no` | `@slow, @scripting` |
| `sdiff` | `set` | `full` | `-` | `-2` | `-` | `no` | `@read, @set, @slow` |
| `sdiffstore` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @slow` |
| `select` | `connection` | `partial` | `-` | `2` | `-` | `no` | `@fast, @connection` |
| `set` | `string` | `full` | `-` | `-3` | `-` | `no` | `@write, @string, @slow` |
| `setbit` | `bitmap` | `full` | `-` | `4` | `-` | `no` | `@write, @bitmap, @slow` |
| `setex` | `string` | `full` | `-` | `4` | `-` | `no` | `@write, @string, @slow` |
| `setnx` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `setrange` | `string` | `full` | `-` | `4` | `-` | `no` | `@write, @string, @slow` |
| `shutdown` | `server` | `full` | `-` | `-1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `sinter` | `set` | `full` | `-` | `-2` | `-` | `no` | `@read, @set, @slow` |
| `sintercard` | `set` | `full` | `-` | `-3` | `-` | `no` | `@read, @set, @slow` |
| `sinterstore` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @slow` |
| `sismember` | `set` | `full` | `-` | `3` | `-` | `no` | `@read, @set, @fast` |
| `slaveof` | `server` | `alias` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `slowlog` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `slowlog|get` | `server` | `partial` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `slowlog|help` | `server` | `partial` | `-` | `2` | `-` | `no` | `@slow` |
| `slowlog|len` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `slowlog|reset` | `server` | `partial` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `smembers` | `set` | `full` | `-` | `2` | `-` | `no` | `@read, @set, @slow` |
| `smismember` | `set` | `full` | `-` | `-3` | `-` | `no` | `@read, @set, @fast` |
| `smove` | `set` | `full` | `-` | `4` | `-` | `no` | `@write, @set, @fast` |
| `sort` | `generic` | `partial` | `-` | `-2` | `-` | `yes` | `@write, @set, @sortedset, @list, @slow, @dangerous` |
| `sort_ro` | `generic` | `full` | `-` | `-2` | `-` | `yes` | `@read, @set, @sortedset, @list, @slow, @dangerous` |
| `spop` | `set` | `full` | `-` | `-2` | `-` | `no` | `@write, @set, @fast` |
| `spublish` | `pubsub` | `deferred` | `v0.9.1` | `3` | `-` | `no` | `@pubsub, @fast` |
| `srandmember` | `set` | `full` | `-` | `-2` | `-` | `no` | `@read, @set, @slow` |
| `srem` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @fast` |
| `sscan` | `set` | `full` | `-` | `-3` | `-` | `yes` | `@read, @set, @slow` |
| `ssubscribe` | `pubsub` | `deferred` | `v0.9.1` | `-2` | `-` | `no` | `@pubsub, @slow` |
| `strlen` | `string` | `full` | `-` | `2` | `-` | `no` | `@read, @string, @fast` |
| `subscribe` | `pubsub` | `partial` | `-` | `-2` | `-` | `no` | `@pubsub, @slow` |
| `substr` | `string` | `alias` | `-` | `4` | `-` | `no` | `@read, @string, @slow` |
| `sunion` | `set` | `full` | `-` | `-2` | `-` | `no` | `@read, @set, @slow` |
| `sunionstore` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @slow` |
| `sunsubscribe` | `pubsub` | `deferred` | `v0.9.1` | `-1` | `-` | `no` | `@pubsub, @slow` |
| `swapdb` | `server` | `partial` | `-` | `3` | `-` | `no` | `@keyspace, @write, @fast, @dangerous` |
| `sync` | `server` | `partial` | `-` | `1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `tdigest.add` | `tdigest` | `deferred` | `v0.9.2` | `-2` | `tdigest` | `no` | `@tdigest, @write, @slow` |
| `tdigest.byrank` | `tdigest` | `deferred` | `v0.9.2` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.byrevrank` | `tdigest` | `deferred` | `v0.9.2` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.cdf` | `tdigest` | `deferred` | `v0.9.2` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.create` | `tdigest` | `deferred` | `v0.9.2` | `-2` | `tdigest` | `no` | `@tdigest, @write` |
| `tdigest.info` | `tdigest` | `deferred` | `v0.9.2` | `2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.max` | `tdigest` | `deferred` | `v0.9.2` | `2` | `tdigest` | `no` | `@tdigest, @read, @fast` |
| `tdigest.merge` | `tdigest` | `deferred` | `v0.9.2` | `-3` | `tdigest` | `no` | `@tdigest, @write, @slow` |
| `tdigest.min` | `tdigest` | `deferred` | `v0.9.2` | `2` | `tdigest` | `no` | `@tdigest, @read, @fast` |
| `tdigest.quantile` | `tdigest` | `deferred` | `v0.9.2` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.rank` | `tdigest` | `deferred` | `v0.9.2` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.reset` | `tdigest` | `deferred` | `v0.9.2` | `2` | `tdigest` | `no` | `@tdigest, @write, @fast` |
| `tdigest.revrank` | `tdigest` | `deferred` | `v0.9.2` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.trimmed_mean` | `tdigest` | `deferred` | `v0.9.2` | `4` | `tdigest` | `no` | `@tdigest, @read` |
| `time` | `server` | `full` | `-` | `1` | `-` | `no` | `@fast` |
| `topk.add` | `topk` | `deferred` | `v0.9.2` | `-2` | `topk` | `no` | `@topk, @write, @slow` |
| `topk.count` | `topk` | `deferred` | `v0.9.2` | `-2` | `topk` | `no` | `@topk, @read, @slow` |
| `topk.incrby` | `topk` | `deferred` | `v0.9.2` | `-2` | `topk` | `no` | `@topk, @write, @slow` |
| `topk.info` | `topk` | `deferred` | `v0.9.2` | `2` | `topk` | `no` | `@topk, @read, @fast` |
| `topk.list` | `topk` | `deferred` | `v0.9.2` | `-2` | `topk` | `no` | `@topk, @read, @slow` |
| `topk.query` | `topk` | `deferred` | `v0.9.2` | `-2` | `topk` | `no` | `@topk, @read, @slow` |
| `topk.reserve` | `topk` | `deferred` | `v0.9.2` | `-3` | `topk` | `no` | `@topk, @write, @fast` |
| `touch` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@keyspace, @read, @fast` |
| `ts.add` | `timeseries` | `deferred` | `v0.9.2` | `-4` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.alter` | `timeseries` | `deferred` | `v0.9.2` | `-2` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.create` | `timeseries` | `deferred` | `v0.9.2` | `-2` | `ts` | `no` | `@timeseries, @write, @fast` |
| `ts.createrule` | `timeseries` | `deferred` | `v0.9.2` | `-6` | `ts` | `no` | `@timeseries, @write, @fast` |
| `ts.decrby` | `timeseries` | `deferred` | `v0.9.2` | `-3` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.del` | `timeseries` | `deferred` | `v0.9.2` | `4` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.deleterule` | `timeseries` | `deferred` | `v0.9.2` | `3` | `ts` | `no` | `@timeseries, @write, @fast` |
| `ts.get` | `timeseries` | `deferred` | `v0.9.2` | `-2` | `ts` | `no` | `@timeseries, @read, @fast` |
| `ts.incrby` | `timeseries` | `deferred` | `v0.9.2` | `-3` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.info` | `timeseries` | `deferred` | `v0.9.2` | `-2` | `ts` | `no` | `@timeseries, @read, @fast` |
| `ts.madd` | `timeseries` | `deferred` | `v0.9.2` | `-1` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.mget` | `timeseries` | `deferred` | `v0.9.2` | `-1` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.mrange` | `timeseries` | `deferred` | `v0.9.2` | `-3` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.mrevrange` | `timeseries` | `deferred` | `v0.9.2` | `-3` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.queryindex` | `timeseries` | `deferred` | `v0.9.2` | `-1` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.range` | `timeseries` | `deferred` | `v0.9.2` | `-4` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.revrange` | `timeseries` | `deferred` | `v0.9.2` | `-4` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ttl` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `type` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `unlink` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@keyspace, @write, @fast` |
| `unsubscribe` | `pubsub` | `partial` | `-` | `-1` | `-` | `no` | `@pubsub, @slow` |
| `unwatch` | `transactions` | `full` | `-` | `1` | `-` | `no` | `@fast, @transaction` |
| `vadd` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vcard` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vdim` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vemb` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vgetattr` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vinfo` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vismember` | `vector_set` | `deferred` | `v0.9.2` | `3` | `vector_set` | `no` | `-` |
| `vlinks` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vrandmember` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vrange` | `vector_set` | `deferred` | `v0.9.2` | `-4` | `vector_set` | `no` | `-` |
| `vrem` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vsetattr` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `vsim` | `vector_set` | `deferred` | `v0.9.2` | `0` | `vector_set` | `no` | `-` |
| `wait` | `generic` | `partial` | `-` | `3` | `-` | `no` | `@slow, @blocking, @connection` |
| `waitaof` | `generic` | `partial` | `-` | `4` | `-` | `no` | `@slow, @blocking, @connection` |
| `watch` | `transactions` | `full` | `-` | `-2` | `-` | `no` | `@fast, @transaction` |
| `xack` | `stream` | `partial` | `-` | `-4` | `-` | `no` | `@write, @stream, @fast` |
| `xackdel` | `stream` | `deferred` | `v0.9.1` | `-6` | `-` | `no` | `@write, @stream, @fast` |
| `xadd` | `stream` | `partial` | `-` | `-5` | `-` | `no` | `@write, @stream, @fast` |
| `xautoclaim` | `stream` | `deferred` | `v0.9.1` | `-6` | `-` | `no` | `@write, @stream, @fast` |
| `xcfgset` | `stream` | `deferred` | `v0.9.1` | `-2` | `-` | `no` | `@write, @stream, @fast` |
| `xclaim` | `stream` | `partial` | `-` | `-6` | `-` | `no` | `@write, @stream, @fast` |
| `xdel` | `stream` | `partial` | `-` | `-3` | `-` | `no` | `@write, @stream, @fast` |
| `xdelex` | `stream` | `deferred` | `v0.9.1` | `-5` | `-` | `no` | `@write, @stream, @fast` |
| `xgroup` | `stream` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `xgroup|create` | `stream` | `partial` | `-` | `-5` | `-` | `no` | `@write, @stream, @slow` |
| `xgroup|createconsumer` | `stream` | `deferred` | `v0.9.1` | `5` | `-` | `no` | `@write, @stream, @slow` |
| `xgroup|delconsumer` | `stream` | `deferred` | `v0.9.1` | `5` | `-` | `no` | `@write, @stream, @slow` |
| `xgroup|destroy` | `stream` | `partial` | `-` | `4` | `-` | `no` | `@write, @stream, @slow` |
| `xgroup|help` | `stream` | `partial` | `-` | `2` | `-` | `no` | `@stream, @slow` |
| `xgroup|setid` | `stream` | `partial` | `-` | `-5` | `-` | `no` | `@write, @stream, @slow` |
| `xidmprecord` | `stream` | `deferred` | `v0.9.1` | `5` | `-` | `no` | `@write, @stream, @fast` |
| `xinfo` | `stream` | `partial` | `-` | `-2` | `-` | `no` | `@slow` |
| `xinfo|consumers` | `stream` | `partial` | `-` | `4` | `-` | `no` | `@read, @stream, @slow` |
| `xinfo|groups` | `stream` | `partial` | `-` | `3` | `-` | `no` | `@read, @stream, @slow` |
| `xinfo|help` | `stream` | `partial` | `-` | `2` | `-` | `no` | `@stream, @slow` |
| `xinfo|stream` | `stream` | `partial` | `-` | `-3` | `-` | `no` | `@read, @stream, @slow` |
| `xlen` | `stream` | `partial` | `-` | `2` | `-` | `no` | `@read, @stream, @fast` |
| `xnack` | `stream` | `deferred` | `v0.9.1` | `-7` | `-` | `no` | `@stream` |
| `xpending` | `stream` | `partial` | `-` | `-3` | `-` | `no` | `@read, @stream, @slow` |
| `xrange` | `stream` | `partial` | `-` | `-4` | `-` | `no` | `@read, @stream, @slow` |
| `xread` | `stream` | `partial` | `-` | `-4` | `-` | `no` | `@read, @stream, @slow, @blocking` |
| `xreadgroup` | `stream` | `deferred` | `v0.9.1` | `-7` | `-` | `no` | `@write, @stream, @slow, @blocking` |
| `xrevrange` | `stream` | `partial` | `-` | `-4` | `-` | `no` | `@read, @stream, @slow` |
| `xsetid` | `stream` | `deferred` | `v0.9.1` | `-3` | `-` | `no` | `@write, @stream, @fast` |
| `xtrim` | `stream` | `partial` | `-` | `-4` | `-` | `no` | `@write, @stream, @slow` |
| `zadd` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @fast` |
| `zcard` | `sorted-set` | `full` | `-` | `2` | `-` | `no` | `@read, @sortedset, @fast` |
| `zcount` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@read, @sortedset, @fast` |
| `zdiff` | `sorted-set` | `partial` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @slow` |
| `zdiffstore` | `sorted-set` | `partial` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zincrby` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@write, @sortedset, @fast` |
| `zinter` | `sorted-set` | `partial` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @slow` |
| `zintercard` | `sorted-set` | `partial` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @slow` |
| `zinterstore` | `sorted-set` | `partial` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zlexcount` | `sorted-set` | `partial` | `-` | `4` | `-` | `no` | `@read, @sortedset, @fast` |
| `zmpop` | `sorted-set` | `partial` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zmscore` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @fast` |
| `zpopmax` | `sorted-set` | `full` | `-` | `-2` | `-` | `no` | `@write, @sortedset, @fast` |
| `zpopmin` | `sorted-set` | `full` | `-` | `-2` | `-` | `no` | `@write, @sortedset, @fast` |
| `zrandmember` | `sorted-set` | `partial` | `-` | `-2` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrange` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrangebylex` | `sorted-set` | `partial` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrangebyscore` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrangestore` | `sorted-set` | `partial` | `-` | `-5` | `-` | `no` | `@write, @sortedset, @slow` |
| `zrank` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @fast` |
| `zrem` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@write, @sortedset, @fast` |
| `zremrangebylex` | `sorted-set` | `partial` | `-` | `4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zremrangebyrank` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zremrangebyscore` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zrevrange` | `sorted-set` | `partial` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrevrangebylex` | `sorted-set` | `partial` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrevrangebyscore` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrevrank` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @fast` |
| `zscan` | `sorted-set` | `full` | `-` | `-3` | `-` | `yes` | `@read, @sortedset, @slow` |
| `zscore` | `sorted-set` | `full` | `-` | `3` | `-` | `no` | `@read, @sortedset, @fast` |
| `zunion` | `sorted-set` | `partial` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @slow` |
| `zunionstore` | `sorted-set` | `partial` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @slow` |
