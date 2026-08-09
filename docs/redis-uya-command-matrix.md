# redis-uya command matrix

> version: v0.9.3-dev
> date: 2026-08-09
> source: Redis 8.6 Commands Reference + `scripts/generate_command_catalog.py`
> runtime source: `src/command/catalog_generated.uya`

## Summary

- tracked official command names: `574`
- tracked top-level command names: `420`
- `COMMAND` / `COMMAND INFO` / `COMMAND DOCS` / `COMMAND LIST` / `COMMAND COUNT` share the same generated catalog
- `v1.0.0` 完成度必须优先按 Tier A / Tier B / Tier C 分层阅读，不能再用总条目数代表当前单机完成度

## Scope tier counts

| tier | tracked official names | tracked top-level names | `full` | `partial` | `standalone-error` | `alias` | `deferred` |
|------|-----------------------:|------------------------:|-------:|----------:|-------------------:|--------:|-----------:|
| Tier A: standalone core | 382 | 265 | 362 | 2 | 15 | 3 | 0 |
| Tier B: mode commands | 34 | 4 | 1 | 0 | 33 | 0 | 0 |
| Tier C: module commands | 158 | 151 | 0 | 0 | 157 | 0 | 1 |

## Status counts

| status | count |
|--------|-------|
| `full` | `363` |
| `partial` | `2` |
| `standalone-error` | `205` |
| `alias` | `3` |
| `deferred` | `1` |

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
| `hash` | `33` |
| `hyperloglog` | `5` |
| `json` | `26` |
| `list` | `24` |
| `pubsub` | `15` |
| `scripting` | `23` |
| `search` | `27` |
| `server` | `90` |
| `set` | `19` |
| `sorted-set` | `35` |
| `stream` | `30` |
| `string` | `26` |
| `suggestion` | `4` |
| `tdigest` | `14` |
| `timeseries` | `21` |
| `topk` | `7` |
| `transactions` | `5` |
| `vector_set` | `13` |

## Matrix

| name | group | status | target | arity | module | pattern | acl |
|------|-------|--------|--------|-------|--------|---------|-----|
| `acl` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `acl|cat` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `acl|deluser` | `server` | `full` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|dryrun` | `server` | `full` | `-` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|genpass` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `acl|getuser` | `server` | `full` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `acl|list` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|load` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|log` | `server` | `full` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|save` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|setuser` | `server` | `full` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|users` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `acl|whoami` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `append` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `arcount` | `array` | `standalone-error` | `v1.1.0` | `2` | `array` | `no` | `@read, @array, @fast` |
| `ardel` | `array` | `standalone-error` | `v1.1.0` | `-3` | `array` | `no` | `@write, @array, @fast` |
| `ardelrange` | `array` | `standalone-error` | `v1.1.0` | `-4` | `array` | `no` | `@write, @array, @slow` |
| `arget` | `array` | `standalone-error` | `v1.1.0` | `3` | `array` | `no` | `@read, @array, @fast` |
| `argetrange` | `array` | `standalone-error` | `v1.1.0` | `4` | `array` | `no` | `@read, @array, @slow` |
| `argrep` | `array` | `standalone-error` | `v1.1.0` | `-6` | `array` | `no` | `@read, @array, @slow` |
| `arinfo` | `array` | `standalone-error` | `v1.1.0` | `-2` | `array` | `no` | `@read, @array, @slow` |
| `arinsert` | `array` | `standalone-error` | `v1.1.0` | `-3` | `array` | `no` | `@write, @array, @fast` |
| `arlastitems` | `array` | `standalone-error` | `v1.1.0` | `-3` | `array` | `no` | `@read, @array, @slow` |
| `arlen` | `array` | `standalone-error` | `v1.1.0` | `2` | `array` | `no` | `@read, @array, @fast` |
| `armget` | `array` | `standalone-error` | `v1.1.0` | `-3` | `array` | `no` | `@read, @array, @fast` |
| `armset` | `array` | `standalone-error` | `v1.1.0` | `-4` | `array` | `no` | `@write, @array, @fast` |
| `arnext` | `array` | `standalone-error` | `v1.1.0` | `2` | `array` | `no` | `@read, @array, @fast` |
| `arop` | `array` | `standalone-error` | `v1.1.0` | `-5` | `array` | `no` | `@read, @array, @slow` |
| `arring` | `array` | `standalone-error` | `v1.1.0` | `-4` | `array` | `no` | `@write, @array, @slow` |
| `arscan` | `array` | `standalone-error` | `v1.1.0` | `-4` | `array` | `no` | `@read, @array, @slow` |
| `arseek` | `array` | `standalone-error` | `v1.1.0` | `3` | `array` | `no` | `@write, @array, @fast` |
| `arset` | `array` | `standalone-error` | `v1.1.0` | `-4` | `array` | `no` | `@write, @array, @fast` |
| `asking` | `cluster` | `standalone-error` | `v1.1.0` | `1` | `-` | `no` | `@fast, @connection` |
| `auth` | `connection` | `full` | `-` | `-2` | `-` | `no` | `@fast, @connection` |
| `backup` | `server` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `backup|abort` | `server` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `backup|cleanup` | `server` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `backup|help` | `server` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `backup|list` | `server` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `backup|seal` | `server` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `backup|start` | `server` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `backup|status` | `server` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `bf.add` | `bf` | `standalone-error` | `v1.1.0` | `3` | `bf` | `no` | `@bloom, @write, @slow` |
| `bf.card` | `bf` | `standalone-error` | `v1.1.0` | `2` | `bf` | `no` | `@bloom, @read, @fast` |
| `bf.exists` | `bf` | `standalone-error` | `v1.1.0` | `3` | `bf` | `no` | `@bloom, @read, @slow` |
| `bf.info` | `bf` | `standalone-error` | `v1.1.0` | `-2` | `bf` | `no` | `@bloom, @read, @fast` |
| `bf.insert` | `bf` | `standalone-error` | `v1.1.0` | `-3` | `bf` | `no` | `@bloom, @write, @slow` |
| `bf.loadchunk` | `bf` | `standalone-error` | `v1.1.0` | `4` | `bf` | `no` | `@bloom, @write, @slow` |
| `bf.madd` | `bf` | `standalone-error` | `v1.1.0` | `-2` | `bf` | `no` | `@bloom, @write, @slow` |
| `bf.mexists` | `bf` | `standalone-error` | `v1.1.0` | `-2` | `bf` | `no` | `@bloom, @read, @slow` |
| `bf.reserve` | `bf` | `standalone-error` | `v1.1.0` | `-4` | `bf` | `no` | `@bloom, @write, @fast` |
| `bf.scandump` | `bf` | `standalone-error` | `v1.1.0` | `3` | `bf` | `no` | `@bloom, @write, @slow` |
| `bgrewriteaof` | `server` | `full` | `-` | `1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `bgsave` | `server` | `full` | `-` | `-1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `bitcount` | `bitmap` | `full` | `-` | `-2` | `-` | `no` | `@read, @bitmap, @slow` |
| `bitfield` | `bitmap` | `full` | `-` | `-2` | `-` | `no` | `@write, @bitmap, @slow` |
| `bitfield_ro` | `bitmap` | `full` | `-` | `-2` | `-` | `no` | `@read, @bitmap, @fast` |
| `bitop` | `bitmap` | `full` | `-` | `-4` | `-` | `no` | `@write, @bitmap, @slow` |
| `bitpos` | `bitmap` | `full` | `-` | `-3` | `-` | `no` | `@read, @bitmap, @slow` |
| `blmove` | `list` | `full` | `-` | `6` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `blmovem` | `list` | `full` | `-` | `-6` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `blmpop` | `list` | `full` | `-` | `-5` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `blpop` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `brpop` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `brpoplpush` | `list` | `full` | `-` | `4` | `-` | `no` | `@write, @list, @slow, @blocking` |
| `bzmpop` | `sorted-set` | `full` | `-` | `-5` | `-` | `no` | `@write, @sortedset, @slow, @blocking` |
| `bzpopmax` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@write, @sortedset, @fast, @blocking` |
| `bzpopmin` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@write, @sortedset, @fast, @blocking` |
| `cf.add` | `cf` | `standalone-error` | `v1.1.0` | `3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.addnx` | `cf` | `standalone-error` | `v1.1.0` | `3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.count` | `cf` | `standalone-error` | `v1.1.0` | `3` | `cf` | `no` | `@cuckoo, @read, @slow` |
| `cf.del` | `cf` | `standalone-error` | `v1.1.0` | `3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.exists` | `cf` | `standalone-error` | `v1.1.0` | `3` | `cf` | `no` | `@cuckoo, @read, @slow` |
| `cf.info` | `cf` | `standalone-error` | `v1.1.0` | `2` | `cf` | `no` | `@cuckoo, @read, @fast` |
| `cf.insert` | `cf` | `standalone-error` | `v1.1.0` | `-3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.insertnx` | `cf` | `standalone-error` | `v1.1.0` | `-3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.loadchunk` | `cf` | `standalone-error` | `v1.1.0` | `4` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `cf.mexists` | `cf` | `standalone-error` | `v1.1.0` | `-2` | `cf` | `no` | `@cuckoo, @read, @slow` |
| `cf.reserve` | `cf` | `standalone-error` | `v1.1.0` | `-3` | `cf` | `no` | `@cuckoo, @write, @fast` |
| `cf.scandump` | `cf` | `standalone-error` | `v1.1.0` | `3` | `cf` | `no` | `@cuckoo, @write, @slow` |
| `client` | `connection` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `client|caching` | `connection` | `full` | `-` | `3` | `-` | `no` | `@slow, @connection` |
| `client|getname` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|getredir` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|help` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|id` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|info` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|kill` | `connection` | `full` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|list` | `connection` | `full` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|no-evict` | `connection` | `full` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|no-touch` | `connection` | `full` | `-` | `3` | `-` | `no` | `@slow, @connection` |
| `client|pause` | `connection` | `full` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|reply` | `connection` | `full` | `-` | `3` | `-` | `no` | `@slow, @connection` |
| `client|setinfo` | `connection` | `full` | `-` | `4` | `-` | `no` | `@slow, @connection` |
| `client|setname` | `connection` | `full` | `-` | `3` | `-` | `no` | `@slow, @connection` |
| `client|tracking` | `connection` | `full` | `-` | `-3` | `-` | `no` | `@slow, @connection` |
| `client|trackinginfo` | `connection` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `client|unblock` | `connection` | `full` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `client|unpause` | `connection` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous, @connection` |
| `cluster` | `cluster` | `standalone-error` | `v1.1.0` | `-2` | `-` | `no` | `@slow` |
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
| `cluster|info` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|keyslot` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@slow` |
| `cluster|links` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|meet` | `cluster` | `standalone-error` | `v1.1.0` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|migration` | `cluster` | `standalone-error` | `v1.1.0` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|myid` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|myshardid` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|nodes` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|replicas` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|replicate` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|reset` | `cluster` | `standalone-error` | `v1.1.0` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|saveconfig` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|set-config-epoch` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|setslot` | `cluster` | `standalone-error` | `v1.1.0` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|shards` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cluster|slaves` | `cluster` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `cluster|slot-stats` | `cluster` | `standalone-error` | `v1.1.0` | `-4` | `-` | `no` | `-` |
| `cluster|slots` | `cluster` | `standalone-error` | `v1.1.0` | `2` | `-` | `no` | `@slow` |
| `cms.incrby` | `cms` | `standalone-error` | `v1.1.0` | `-2` | `cms` | `no` | `@cms, @write` |
| `cms.info` | `cms` | `standalone-error` | `v1.1.0` | `2` | `cms` | `no` | `@cms, @read, @fast` |
| `cms.initbydim` | `cms` | `standalone-error` | `v1.1.0` | `4` | `cms` | `no` | `@cms, @write, @fast` |
| `cms.initbyprob` | `cms` | `standalone-error` | `v1.1.0` | `4` | `cms` | `no` | `@cms, @write, @fast` |
| `cms.merge` | `cms` | `standalone-error` | `v1.1.0` | `-3` | `cms` | `no` | `@cms, @write` |
| `cms.query` | `cms` | `standalone-error` | `v1.1.0` | `-2` | `cms` | `no` | `@cms, @read` |
| `command` | `server` | `full` | `-` | `-1` | `-` | `no` | `@slow, @connection` |
| `command|count` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `command|docs` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow, @connection` |
| `command|getkeys` | `server` | `full` | `-` | `-3` | `-` | `no` | `@slow, @connection` |
| `command|getkeysandflags` | `server` | `full` | `-` | `-3` | `-` | `no` | `@slow, @connection` |
| `command|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow, @connection` |
| `command|info` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow, @connection` |
| `command|list` | `server` | `full` | `-` | `-2` | `-` | `yes` | `@slow, @connection` |
| `config` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `config|get` | `server` | `full` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `config|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `config|resetstat` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `config|rewrite` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `config|set` | `server` | `full` | `-` | `-4` | `-` | `no` | `@admin, @slow, @dangerous` |
| `copy` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @slow` |
| `dbsize` | `server` | `full` | `-` | `1` | `-` | `no` | `@keyspace, @read, @fast` |
| `debug` | `server` | `standalone-error` | `v1.1.0` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `decr` | `string` | `full` | `-` | `2` | `-` | `no` | `@write, @string, @fast` |
| `decrby` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `del` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@keyspace, @write, @slow` |
| `delex` | `string` | `full` | `-` | `-2` | `-` | `no` | `@write, @string, @fast` |
| `digest` | `string` | `full` | `-` | `2` | `-` | `no` | `@read, @string, @fast` |
| `discard` | `transactions` | `full` | `-` | `1` | `-` | `no` | `@fast, @transaction` |
| `dump` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @slow` |
| `echo` | `connection` | `full` | `-` | `2` | `-` | `no` | `@fast, @connection` |
| `eval` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `eval_ro` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `evalsha` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `evalsha_ro` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `exec` | `transactions` | `full` | `-` | `1` | `-` | `no` | `@slow, @transaction` |
| `exists` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@keyspace, @read, @fast` |
| `expire` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @fast` |
| `expireat` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @fast` |
| `expiretime` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `failover` | `server` | `standalone-error` | `v1.1.0` | `-1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `fcall` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `fcall_ro` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `flushall` | `server` | `full` | `-` | `-1` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `flushdb` | `server` | `full` | `-` | `-1` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `ft._list` | `search` | `standalone-error` | `v1.1.0` | `0` | `ft` | `no` | `@admin, @search, @slow` |
| `ft.aggregate` | `search` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@search, @read, @fast` |
| `ft.aliasadd` | `search` | `standalone-error` | `v1.1.0` | `3` | `ft` | `no` | `@search` |
| `ft.aliasdel` | `search` | `standalone-error` | `v1.1.0` | `2` | `ft` | `no` | `@search` |
| `ft.aliaslist` | `search` | `deferred` | `v0.9.2` | `2` | `ft` | `no` | `@search` |
| `ft.aliasupdate` | `search` | `standalone-error` | `v1.1.0` | `3` | `ft` | `no` | `@search` |
| `ft.alter` | `search` | `standalone-error` | `v1.1.0` | `-6` | `ft` | `no` | `@search` |
| `ft.config|get` | `search` | `standalone-error` | `v1.1.0` | `2` | `ft` | `no` | `@admin, @search` |
| `ft.config|help` | `search` | `standalone-error` | `v1.1.0` | `2` | `ft` | `no` | `@admin, @search` |
| `ft.config|set` | `search` | `standalone-error` | `v1.1.0` | `3` | `ft` | `no` | `@admin, @search` |
| `ft.create` | `search` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@search` |
| `ft.cursor|del` | `search` | `standalone-error` | `v1.1.0` | `3` | `ft` | `no` | `@read, @search` |
| `ft.cursor|read` | `search` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@read, @search` |
| `ft.dictadd` | `search` | `standalone-error` | `v1.1.0` | `-2` | `ft` | `no` | `@search` |
| `ft.dictdel` | `search` | `standalone-error` | `v1.1.0` | `-2` | `ft` | `no` | `@search` |
| `ft.dictdump` | `search` | `standalone-error` | `v1.1.0` | `2` | `ft` | `no` | `@search` |
| `ft.dropindex` | `search` | `standalone-error` | `v1.1.0` | `-2` | `ft` | `no` | `@dangerous, @search, @slow, @write` |
| `ft.explain` | `search` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@search` |
| `ft.explaincli` | `search` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@search` |
| `ft.hybrid` | `search` | `standalone-error` | `v1.1.0` | `-7` | `ft` | `no` | `@read, @search` |
| `ft.info` | `search` | `standalone-error` | `v1.1.0` | `2` | `ft` | `no` | `@search` |
| `ft.profile` | `search` | `standalone-error` | `v1.1.0` | `-5` | `ft` | `no` | `@read, @search` |
| `ft.search` | `search` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@read, @search` |
| `ft.spellcheck` | `search` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@search` |
| `ft.sugadd` | `suggestion` | `standalone-error` | `v1.1.0` | `-4` | `ft` | `no` | `@search, @write` |
| `ft.sugdel` | `suggestion` | `standalone-error` | `v1.1.0` | `3` | `ft` | `no` | `@search, @write` |
| `ft.sugget` | `suggestion` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@search` |
| `ft.suglen` | `suggestion` | `standalone-error` | `v1.1.0` | `2` | `ft` | `no` | `@search` |
| `ft.syndump` | `search` | `standalone-error` | `v1.1.0` | `2` | `ft` | `no` | `@search` |
| `ft.synupdate` | `search` | `standalone-error` | `v1.1.0` | `-3` | `ft` | `no` | `@search` |
| `ft.tagvals` | `search` | `standalone-error` | `v1.1.0` | `3` | `ft` | `no` | `@dangerous, @read, @search, @slow` |
| `function` | `scripting` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `function|delete` | `scripting` | `full` | `-` | `3` | `-` | `no` | `@write, @slow, @scripting` |
| `function|dump` | `scripting` | `full` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `function|flush` | `scripting` | `full` | `-` | `-2` | `-` | `no` | `@write, @slow, @scripting` |
| `function|help` | `scripting` | `full` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `function|kill` | `scripting` | `full` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `function|list` | `scripting` | `full` | `-` | `-2` | `-` | `no` | `@slow, @scripting` |
| `function|load` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@write, @slow, @scripting` |
| `function|restore` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@write, @slow, @scripting` |
| `function|stats` | `scripting` | `full` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `geoadd` | `geo` | `full` | `-` | `-5` | `-` | `no` | `@write, @geo, @slow` |
| `geodist` | `geo` | `full` | `-` | `-4` | `-` | `no` | `@read, @geo, @slow` |
| `geohash` | `geo` | `full` | `-` | `-2` | `-` | `no` | `@read, @geo, @slow` |
| `geopos` | `geo` | `full` | `-` | `-2` | `-` | `no` | `@read, @geo, @slow` |
| `georadius` | `geo` | `full` | `-` | `-6` | `-` | `no` | `@write, @geo, @slow` |
| `georadius_ro` | `geo` | `full` | `-` | `-6` | `-` | `no` | `@read, @geo, @slow` |
| `georadiusbymember` | `geo` | `full` | `-` | `-5` | `-` | `no` | `@write, @geo, @slow` |
| `georadiusbymember_ro` | `geo` | `full` | `-` | `-5` | `-` | `no` | `@read, @geo, @slow` |
| `geosearch` | `geo` | `full` | `-` | `-7` | `-` | `no` | `@read, @geo, @slow` |
| `geosearchstore` | `geo` | `full` | `-` | `-8` | `-` | `no` | `@write, @geo, @slow` |
| `get` | `string` | `full` | `-` | `2` | `-` | `no` | `@read, @string, @fast` |
| `getbit` | `bitmap` | `full` | `-` | `3` | `-` | `no` | `@read, @bitmap, @fast` |
| `getdel` | `string` | `full` | `-` | `2` | `-` | `no` | `@write, @string, @fast` |
| `getex` | `string` | `full` | `-` | `-2` | `-` | `no` | `@write, @string, @fast` |
| `getrange` | `string` | `full` | `-` | `4` | `-` | `no` | `@read, @string, @slow` |
| `getset` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `hdel` | `hash` | `full` | `-` | `-3` | `-` | `no` | `@write, @hash, @fast` |
| `hello` | `connection` | `full` | `-` | `-1` | `-` | `no` | `@fast, @connection` |
| `hexists` | `hash` | `full` | `-` | `3` | `-` | `no` | `@read, @hash, @fast` |
| `hexpire` | `hash` | `full` | `-` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hexpireat` | `hash` | `full` | `-` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hexpiretime` | `hash` | `full` | `-` | `-5` | `-` | `no` | `@read, @hash, @fast` |
| `hget` | `hash` | `full` | `-` | `3` | `-` | `no` | `@read, @hash, @fast` |
| `hgetall` | `hash` | `full` | `-` | `2` | `-` | `no` | `@read, @hash, @slow` |
| `hgetdel` | `hash` | `full` | `-` | `-5` | `-` | `no` | `@write, @hash, @fast` |
| `hgetex` | `hash` | `full` | `-` | `-5` | `-` | `no` | `@write, @hash, @fast` |
| `himport` | `hash` | `full` | `-` | `-2` | `-` | `no` | `@hash, @slow` |
| `himport|discard` | `hash` | `full` | `-` | `3` | `-` | `no` | `@hash, @slow` |
| `himport|discardall` | `hash` | `full` | `-` | `2` | `-` | `no` | `@hash, @slow` |
| `himport|prepare` | `hash` | `full` | `-` | `-4` | `-` | `no` | `@hash, @slow` |
| `himport|set` | `hash` | `full` | `-` | `-5` | `-` | `no` | `@write, @hash, @slow` |
| `hincrby` | `hash` | `full` | `-` | `4` | `-` | `no` | `@write, @hash, @fast` |
| `hincrbyfloat` | `hash` | `full` | `-` | `4` | `-` | `no` | `@write, @hash, @fast` |
| `hkeys` | `hash` | `full` | `-` | `2` | `-` | `no` | `@read, @hash, @slow` |
| `hlen` | `hash` | `full` | `-` | `2` | `-` | `no` | `@read, @hash, @fast` |
| `hmget` | `hash` | `full` | `-` | `-3` | `-` | `no` | `@read, @hash, @fast` |
| `hmset` | `hash` | `alias` | `-` | `-4` | `-` | `no` | `@write, @hash, @fast` |
| `hotkeys` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `hotkeys|get` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `hotkeys|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin` |
| `hotkeys|reset` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `hotkeys|start` | `server` | `full` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `hotkeys|stop` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `hpersist` | `hash` | `full` | `-` | `-5` | `-` | `no` | `@write, @hash, @fast` |
| `hpexpire` | `hash` | `full` | `-` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hpexpireat` | `hash` | `full` | `-` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hpexpiretime` | `hash` | `full` | `-` | `-5` | `-` | `no` | `@read, @hash, @fast` |
| `hpttl` | `hash` | `full` | `-` | `-5` | `-` | `no` | `@read, @hash, @fast` |
| `hrandfield` | `hash` | `full` | `-` | `-2` | `-` | `no` | `@read, @hash, @slow` |
| `hscan` | `hash` | `full` | `-` | `-3` | `-` | `yes` | `@read, @hash, @slow` |
| `hset` | `hash` | `full` | `-` | `-4` | `-` | `no` | `@write, @hash, @fast` |
| `hsetex` | `hash` | `full` | `-` | `-6` | `-` | `no` | `@write, @hash, @fast` |
| `hsetnx` | `hash` | `full` | `-` | `4` | `-` | `no` | `@write, @hash, @fast` |
| `hstrlen` | `hash` | `full` | `-` | `3` | `-` | `no` | `@read, @hash, @fast` |
| `httl` | `hash` | `full` | `-` | `-5` | `-` | `no` | `@read, @hash, @fast` |
| `hvals` | `hash` | `full` | `-` | `2` | `-` | `no` | `@read, @hash, @slow` |
| `incr` | `string` | `full` | `-` | `2` | `-` | `no` | `@write, @string, @fast` |
| `incrby` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `incrbyfloat` | `string` | `full` | `-` | `3` | `-` | `no` | `@write, @string, @fast` |
| `increx` | `string` | `full` | `-` | `-2` | `-` | `no` | `@fast, @string, @write` |
| `info` | `server` | `full` | `-` | `-1` | `-` | `no` | `@slow, @dangerous` |
| `json.arrappend` | `json` | `standalone-error` | `v1.1.0` | `-3` | `json` | `no` | `@json, @write, @slow` |
| `json.arrindex` | `json` | `standalone-error` | `v1.1.0` | `-4` | `json` | `no` | `@json, @read, @slow` |
| `json.arrinsert` | `json` | `standalone-error` | `v1.1.0` | `-4` | `json` | `no` | `@json, @write, @slow` |
| `json.arrlen` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.arrpop` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @write, @slow` |
| `json.arrtrim` | `json` | `standalone-error` | `v1.1.0` | `5` | `json` | `no` | `@json, @write, @slow` |
| `json.clear` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @write, @slow` |
| `json.debug` | `json` | `standalone-error` | `v1.1.0` | `0` | `json` | `no` | `-` |
| `json.debug|help` | `json` | `standalone-error` | `v1.1.0` | `0` | `json` | `no` | `-` |
| `json.debug|memory` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read` |
| `json.del` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @write, @slow` |
| `json.forget` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @write, @slow` |
| `json.get` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.merge` | `json` | `standalone-error` | `v1.1.0` | `4` | `json` | `no` | `@json, @write, @slow` |
| `json.mget` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.mset` | `json` | `standalone-error` | `v1.1.0` | `-1` | `json` | `no` | `@json, @write, @slow` |
| `json.numincrby` | `json` | `standalone-error` | `v1.1.0` | `4` | `json` | `no` | `@json, @write, @slow` |
| `json.nummultby` | `json` | `standalone-error` | `v1.1.0` | `4` | `json` | `no` | `@json, @write, @slow` |
| `json.objkeys` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.objlen` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.resp` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.set` | `json` | `standalone-error` | `v1.1.0` | `-4` | `json` | `no` | `@json, @write, @slow` |
| `json.strappend` | `json` | `standalone-error` | `v1.1.0` | `-3` | `json` | `no` | `@json, @write, @slow` |
| `json.strlen` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `json.toggle` | `json` | `standalone-error` | `v1.1.0` | `3` | `json` | `no` | `@json, @write, @slow` |
| `json.type` | `json` | `standalone-error` | `v1.1.0` | `-2` | `json` | `no` | `@json, @read, @slow` |
| `keys` | `generic` | `full` | `-` | `2` | `-` | `yes` | `@keyspace, @read, @slow, @dangerous` |
| `lastsave` | `server` | `full` | `-` | `1` | `-` | `no` | `@admin, @fast, @dangerous` |
| `latency` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `latency|doctor` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|graph` | `server` | `full` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `latency|histogram` | `server` | `full` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|history` | `server` | `full` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|latest` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `latency|reset` | `server` | `full` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `lcs` | `string` | `full` | `-` | `-3` | `-` | `no` | `@read, @string, @slow` |
| `lindex` | `list` | `full` | `-` | `3` | `-` | `no` | `@read, @list, @slow` |
| `linsert` | `list` | `full` | `-` | `5` | `-` | `no` | `@write, @list, @slow` |
| `llen` | `list` | `full` | `-` | `2` | `-` | `no` | `@read, @list, @fast` |
| `lmove` | `list` | `full` | `-` | `5` | `-` | `no` | `@write, @list, @slow` |
| `lmovem` | `list` | `full` | `-` | `-5` | `-` | `no` | `@write, @list, @slow` |
| `lmpop` | `list` | `full` | `-` | `-4` | `-` | `no` | `@write, @list, @slow` |
| `lolwut` | `server` | `full` | `-` | `-1` | `-` | `no` | `@read, @fast` |
| `lpop` | `list` | `full` | `-` | `-2` | `-` | `no` | `@write, @list, @fast` |
| `lpos` | `list` | `full` | `-` | `-3` | `-` | `no` | `@read, @list, @slow` |
| `lpush` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @fast` |
| `lpushx` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @fast` |
| `lrange` | `list` | `full` | `-` | `4` | `-` | `no` | `@read, @list, @slow` |
| `lrem` | `list` | `full` | `-` | `4` | `-` | `no` | `@write, @list, @slow` |
| `lset` | `list` | `full` | `-` | `4` | `-` | `no` | `@write, @list, @slow` |
| `ltrim` | `list` | `full` | `-` | `4` | `-` | `no` | `@write, @list, @slow` |
| `memory` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `memory|doctor` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|malloc-stats` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|purge` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|stats` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `memory|usage` | `server` | `full` | `-` | `-3` | `-` | `no` | `@read, @slow` |
| `mget` | `string` | `full` | `-` | `-2` | `-` | `no` | `@read, @string, @fast` |
| `migrate` | `generic` | `standalone-error` | `v1.1.0` | `-6` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `module` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `module|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `module|list` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `module|load` | `server` | `standalone-error` | `v1.1.0` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `module|loadex` | `server` | `standalone-error` | `v1.1.0` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `module|unload` | `server` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `monitor` | `server` | `full` | `-` | `1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `move` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @write, @fast` |
| `mset` | `string` | `full` | `-` | `-3` | `-` | `no` | `@write, @string, @slow` |
| `msetex` | `string` | `full` | `-` | `-4` | `-` | `no` | `@write, @string, @slow` |
| `msetnx` | `string` | `full` | `-` | `-3` | `-` | `no` | `@write, @string, @slow` |
| `multi` | `transactions` | `full` | `-` | `1` | `-` | `no` | `@fast, @transaction` |
| `object` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `object|encoding` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @read, @slow` |
| `object|freq` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @read, @slow` |
| `object|help` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @slow` |
| `object|idletime` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @read, @slow` |
| `object|refcount` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @read, @slow` |
| `persist` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @write, @fast` |
| `pexpire` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @fast` |
| `pexpireat` | `generic` | `full` | `-` | `-3` | `-` | `no` | `@keyspace, @write, @fast` |
| `pexpiretime` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `pfadd` | `hyperloglog` | `full` | `-` | `-2` | `-` | `no` | `@write, @hyperloglog, @fast` |
| `pfcount` | `hyperloglog` | `full` | `-` | `-2` | `-` | `no` | `@read, @hyperloglog, @slow` |
| `pfdebug` | `hyperloglog` | `standalone-error` | `v1.1.0` | `3` | `-` | `no` | `@write, @hyperloglog, @admin, @slow, @dangerous` |
| `pfmerge` | `hyperloglog` | `full` | `-` | `-2` | `-` | `no` | `@write, @hyperloglog, @slow` |
| `pfselftest` | `hyperloglog` | `full` | `-` | `1` | `-` | `no` | `@hyperloglog, @admin, @slow, @dangerous` |
| `ping` | `connection` | `full` | `-` | `-1` | `-` | `no` | `@fast, @connection` |
| `psetex` | `string` | `full` | `-` | `4` | `-` | `no` | `@write, @string, @slow` |
| `psubscribe` | `pubsub` | `full` | `-` | `-2` | `-` | `yes` | `@pubsub, @slow` |
| `psync` | `server` | `full` | `-` | `-3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `pttl` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `publish` | `pubsub` | `full` | `-` | `3` | `-` | `no` | `@pubsub, @fast` |
| `pubsub` | `pubsub` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `pubsub|channels` | `pubsub` | `full` | `-` | `-2` | `-` | `yes` | `@pubsub, @slow` |
| `pubsub|help` | `pubsub` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `pubsub|numpat` | `pubsub` | `full` | `-` | `2` | `-` | `no` | `@pubsub, @slow` |
| `pubsub|numsub` | `pubsub` | `full` | `-` | `-2` | `-` | `no` | `@pubsub, @slow` |
| `pubsub|shardchannels` | `pubsub` | `partial` | `-` | `-2` | `-` | `yes` | `@pubsub, @slow` |
| `pubsub|shardnumsub` | `pubsub` | `partial` | `-` | `-2` | `-` | `no` | `@pubsub, @slow` |
| `punsubscribe` | `pubsub` | `full` | `-` | `-1` | `-` | `yes` | `@pubsub, @slow` |
| `quit` | `connection` | `full` | `-` | `-1` | `-` | `no` | `@fast, @connection` |
| `randomkey` | `generic` | `full` | `-` | `1` | `-` | `no` | `@keyspace, @read, @slow` |
| `readonly` | `cluster` | `standalone-error` | `v1.1.0` | `1` | `-` | `no` | `@fast, @connection` |
| `readwrite` | `cluster` | `standalone-error` | `v1.1.0` | `1` | `-` | `no` | `@fast, @connection` |
| `rename` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @write, @slow` |
| `renamenx` | `generic` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @write, @fast` |
| `replconf` | `server` | `full` | `-` | `-1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `replicaof` | `server` | `full` | `-` | `3` | `-` | `no` | `@admin, @slow, @dangerous` |
| `reset` | `connection` | `full` | `-` | `1` | `-` | `no` | `@fast, @connection` |
| `restore` | `generic` | `full` | `-` | `-4` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `restore-asking` | `server` | `full` | `-` | `-4` | `-` | `no` | `@keyspace, @write, @slow, @dangerous` |
| `role` | `server` | `full` | `-` | `1` | `-` | `no` | `@admin, @fast, @dangerous` |
| `rpop` | `list` | `full` | `-` | `-2` | `-` | `no` | `@write, @list, @fast` |
| `rpoplpush` | `list` | `full` | `-` | `3` | `-` | `no` | `@write, @list, @slow` |
| `rpush` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @fast` |
| `rpushx` | `list` | `full` | `-` | `-3` | `-` | `no` | `@write, @list, @fast` |
| `sadd` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @fast` |
| `save` | `server` | `full` | `-` | `1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `scan` | `generic` | `full` | `-` | `-2` | `-` | `yes` | `@keyspace, @read, @slow` |
| `scard` | `set` | `full` | `-` | `2` | `-` | `no` | `@read, @set, @fast` |
| `script` | `scripting` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `script|debug` | `scripting` | `full` | `-` | `3` | `-` | `no` | `@slow, @scripting` |
| `script|exists` | `scripting` | `full` | `-` | `-3` | `-` | `no` | `@slow, @scripting` |
| `script|flush` | `scripting` | `full` | `-` | `-2` | `-` | `no` | `@slow, @scripting` |
| `script|help` | `scripting` | `full` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `script|kill` | `scripting` | `full` | `-` | `2` | `-` | `no` | `@slow, @scripting` |
| `script|load` | `scripting` | `full` | `-` | `3` | `-` | `no` | `@slow, @scripting` |
| `sdiff` | `set` | `full` | `-` | `-2` | `-` | `no` | `@read, @set, @slow` |
| `sdiffcard` | `set` | `full` | `-` | `-3` | `-` | `no` | `@read, @set, @slow` |
| `sdiffstore` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @slow` |
| `select` | `connection` | `full` | `-` | `2` | `-` | `no` | `@fast, @connection` |
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
| `slowlog` | `server` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `slowlog|get` | `server` | `full` | `-` | `-2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `slowlog|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |
| `slowlog|len` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `slowlog|reset` | `server` | `full` | `-` | `2` | `-` | `no` | `@admin, @slow, @dangerous` |
| `smembers` | `set` | `full` | `-` | `2` | `-` | `no` | `@read, @set, @slow` |
| `smismember` | `set` | `full` | `-` | `-3` | `-` | `no` | `@read, @set, @fast` |
| `smove` | `set` | `full` | `-` | `4` | `-` | `no` | `@write, @set, @fast` |
| `sort` | `generic` | `full` | `-` | `-2` | `-` | `yes` | `@write, @set, @sortedset, @list, @slow, @dangerous` |
| `sort_ro` | `generic` | `full` | `-` | `-2` | `-` | `yes` | `@read, @set, @sortedset, @list, @slow, @dangerous` |
| `spop` | `set` | `full` | `-` | `-2` | `-` | `no` | `@write, @set, @fast` |
| `spublish` | `pubsub` | `full` | `-` | `3` | `-` | `no` | `@pubsub, @fast` |
| `srandmember` | `set` | `full` | `-` | `-2` | `-` | `no` | `@read, @set, @slow` |
| `srem` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @fast` |
| `sscan` | `set` | `full` | `-` | `-3` | `-` | `yes` | `@read, @set, @slow` |
| `ssubscribe` | `pubsub` | `full` | `-` | `-2` | `-` | `no` | `@pubsub, @slow` |
| `strlen` | `string` | `full` | `-` | `2` | `-` | `no` | `@read, @string, @fast` |
| `subscribe` | `pubsub` | `full` | `-` | `-2` | `-` | `no` | `@pubsub, @slow` |
| `substr` | `string` | `alias` | `-` | `4` | `-` | `no` | `@read, @string, @slow` |
| `sunion` | `set` | `full` | `-` | `-2` | `-` | `no` | `@read, @set, @slow` |
| `sunioncard` | `set` | `full` | `-` | `-3` | `-` | `no` | `@read, @set, @slow` |
| `sunionstore` | `set` | `full` | `-` | `-3` | `-` | `no` | `@write, @set, @slow` |
| `sunsubscribe` | `pubsub` | `full` | `-` | `-1` | `-` | `no` | `@pubsub, @slow` |
| `swapdb` | `server` | `full` | `-` | `3` | `-` | `no` | `@keyspace, @write, @fast, @dangerous` |
| `sync` | `server` | `full` | `-` | `1` | `-` | `no` | `@admin, @slow, @dangerous` |
| `tdigest.add` | `tdigest` | `standalone-error` | `v1.1.0` | `-2` | `tdigest` | `no` | `@tdigest, @write, @slow` |
| `tdigest.byrank` | `tdigest` | `standalone-error` | `v1.1.0` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.byrevrank` | `tdigest` | `standalone-error` | `v1.1.0` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.cdf` | `tdigest` | `standalone-error` | `v1.1.0` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.create` | `tdigest` | `standalone-error` | `v1.1.0` | `-2` | `tdigest` | `no` | `@tdigest, @write` |
| `tdigest.info` | `tdigest` | `standalone-error` | `v1.1.0` | `2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.max` | `tdigest` | `standalone-error` | `v1.1.0` | `2` | `tdigest` | `no` | `@tdigest, @read, @fast` |
| `tdigest.merge` | `tdigest` | `standalone-error` | `v1.1.0` | `-3` | `tdigest` | `no` | `@tdigest, @write, @slow` |
| `tdigest.min` | `tdigest` | `standalone-error` | `v1.1.0` | `2` | `tdigest` | `no` | `@tdigest, @read, @fast` |
| `tdigest.quantile` | `tdigest` | `standalone-error` | `v1.1.0` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.rank` | `tdigest` | `standalone-error` | `v1.1.0` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.reset` | `tdigest` | `standalone-error` | `v1.1.0` | `2` | `tdigest` | `no` | `@tdigest, @write, @fast` |
| `tdigest.revrank` | `tdigest` | `standalone-error` | `v1.1.0` | `-2` | `tdigest` | `no` | `@tdigest, @read` |
| `tdigest.trimmed_mean` | `tdigest` | `standalone-error` | `v1.1.0` | `4` | `tdigest` | `no` | `@tdigest, @read` |
| `time` | `server` | `full` | `-` | `1` | `-` | `no` | `@fast` |
| `topk.add` | `topk` | `standalone-error` | `v1.1.0` | `-2` | `topk` | `no` | `@topk, @write, @slow` |
| `topk.count` | `topk` | `standalone-error` | `v1.1.0` | `-2` | `topk` | `no` | `@topk, @read, @slow` |
| `topk.incrby` | `topk` | `standalone-error` | `v1.1.0` | `-2` | `topk` | `no` | `@topk, @write, @slow` |
| `topk.info` | `topk` | `standalone-error` | `v1.1.0` | `2` | `topk` | `no` | `@topk, @read, @fast` |
| `topk.list` | `topk` | `standalone-error` | `v1.1.0` | `-2` | `topk` | `no` | `@topk, @read, @slow` |
| `topk.query` | `topk` | `standalone-error` | `v1.1.0` | `-2` | `topk` | `no` | `@topk, @read, @slow` |
| `topk.reserve` | `topk` | `standalone-error` | `v1.1.0` | `-3` | `topk` | `no` | `@topk, @write, @fast` |
| `touch` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@keyspace, @read, @fast` |
| `ts.add` | `timeseries` | `standalone-error` | `v1.1.0` | `-4` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.alter` | `timeseries` | `standalone-error` | `v1.1.0` | `-2` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.create` | `timeseries` | `standalone-error` | `v1.1.0` | `-2` | `ts` | `no` | `@timeseries, @write, @fast` |
| `ts.createrule` | `timeseries` | `standalone-error` | `v1.1.0` | `-6` | `ts` | `no` | `@timeseries, @write, @fast` |
| `ts.decrby` | `timeseries` | `standalone-error` | `v1.1.0` | `-3` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.del` | `timeseries` | `standalone-error` | `v1.1.0` | `4` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.deleterule` | `timeseries` | `standalone-error` | `v1.1.0` | `3` | `ts` | `no` | `@timeseries, @write, @fast` |
| `ts.get` | `timeseries` | `standalone-error` | `v1.1.0` | `-2` | `ts` | `no` | `@timeseries, @read, @fast` |
| `ts.incrby` | `timeseries` | `standalone-error` | `v1.1.0` | `-3` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.info` | `timeseries` | `standalone-error` | `v1.1.0` | `-2` | `ts` | `no` | `@timeseries, @read, @fast` |
| `ts.madd` | `timeseries` | `standalone-error` | `v1.1.0` | `-1` | `ts` | `no` | `@timeseries, @write, @slow` |
| `ts.mget` | `timeseries` | `standalone-error` | `v1.1.0` | `-1` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.mrange` | `timeseries` | `standalone-error` | `v1.1.0` | `-3` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.mrevrange` | `timeseries` | `standalone-error` | `v1.1.0` | `-3` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.nrange` | `timeseries` | `standalone-error` | `v1.1.0` | `-5` | `ts` | `no` | `@read, @timeseries` |
| `ts.nrevrange` | `timeseries` | `standalone-error` | `v1.1.0` | `-5` | `ts` | `no` | `@read, @timeseries` |
| `ts.queryindex` | `timeseries` | `standalone-error` | `v1.1.0` | `-1` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.querylabels` | `timeseries` | `standalone-error` | `v1.1.0` | `-2` | `ts` | `no` | `@read, @timeseries` |
| `ts.range` | `timeseries` | `standalone-error` | `v1.1.0` | `-4` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ts.read` | `timeseries` | `standalone-error` | `v1.1.0` | `-3` | `ts` | `no` | `@read, @timeseries` |
| `ts.revrange` | `timeseries` | `standalone-error` | `v1.1.0` | `-4` | `ts` | `no` | `@timeseries, @read, @slow` |
| `ttl` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `type` | `generic` | `full` | `-` | `2` | `-` | `no` | `@keyspace, @read, @fast` |
| `unlink` | `generic` | `full` | `-` | `-2` | `-` | `no` | `@keyspace, @write, @fast` |
| `unsubscribe` | `pubsub` | `full` | `-` | `-1` | `-` | `no` | `@pubsub, @slow` |
| `unwatch` | `transactions` | `full` | `-` | `1` | `-` | `no` | `@fast, @transaction` |
| `vadd` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vcard` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vdim` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vemb` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vgetattr` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vinfo` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vismember` | `vector_set` | `standalone-error` | `v1.1.0` | `3` | `vector_set` | `no` | `-` |
| `vlinks` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vrandmember` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vrange` | `vector_set` | `standalone-error` | `v1.1.0` | `-4` | `vector_set` | `no` | `-` |
| `vrem` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vsetattr` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `vsim` | `vector_set` | `standalone-error` | `v1.1.0` | `0` | `vector_set` | `no` | `-` |
| `wait` | `generic` | `full` | `-` | `3` | `-` | `no` | `@slow, @blocking, @connection` |
| `waitaof` | `generic` | `full` | `-` | `4` | `-` | `no` | `@slow, @blocking, @connection` |
| `watch` | `transactions` | `full` | `-` | `-2` | `-` | `no` | `@fast, @transaction` |
| `xack` | `stream` | `full` | `-` | `-4` | `-` | `no` | `@write, @stream, @fast` |
| `xackdel` | `stream` | `full` | `-` | `-6` | `-` | `no` | `@write, @stream, @fast` |
| `xadd` | `stream` | `full` | `-` | `-5` | `-` | `no` | `@write, @stream, @fast` |
| `xautoclaim` | `stream` | `full` | `-` | `-6` | `-` | `no` | `@write, @stream, @fast` |
| `xcfgset` | `stream` | `full` | `-` | `-2` | `-` | `no` | `@write, @stream, @fast` |
| `xclaim` | `stream` | `full` | `-` | `-6` | `-` | `no` | `@write, @stream, @fast` |
| `xdel` | `stream` | `full` | `-` | `-3` | `-` | `no` | `@write, @stream, @fast` |
| `xdelex` | `stream` | `full` | `-` | `-5` | `-` | `no` | `@write, @stream, @fast` |
| `xgroup` | `stream` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `xgroup|create` | `stream` | `full` | `-` | `-5` | `-` | `no` | `@write, @stream, @slow` |
| `xgroup|createconsumer` | `stream` | `full` | `-` | `5` | `-` | `no` | `@write, @stream, @slow` |
| `xgroup|delconsumer` | `stream` | `full` | `-` | `5` | `-` | `no` | `@write, @stream, @slow` |
| `xgroup|destroy` | `stream` | `full` | `-` | `4` | `-` | `no` | `@write, @stream, @slow` |
| `xgroup|help` | `stream` | `full` | `-` | `2` | `-` | `no` | `@stream, @slow` |
| `xgroup|setid` | `stream` | `full` | `-` | `-5` | `-` | `no` | `@write, @stream, @slow` |
| `xidmprecord` | `stream` | `full` | `-` | `5` | `-` | `no` | `@write, @stream, @fast` |
| `xinfo` | `stream` | `full` | `-` | `-2` | `-` | `no` | `@slow` |
| `xinfo|consumers` | `stream` | `full` | `-` | `4` | `-` | `no` | `@read, @stream, @slow` |
| `xinfo|groups` | `stream` | `full` | `-` | `3` | `-` | `no` | `@read, @stream, @slow` |
| `xinfo|help` | `stream` | `full` | `-` | `2` | `-` | `no` | `@stream, @slow` |
| `xinfo|stream` | `stream` | `full` | `-` | `-3` | `-` | `no` | `@read, @stream, @slow` |
| `xlen` | `stream` | `full` | `-` | `2` | `-` | `no` | `@read, @stream, @fast` |
| `xnack` | `stream` | `full` | `-` | `-7` | `-` | `no` | `@stream` |
| `xpending` | `stream` | `full` | `-` | `-3` | `-` | `no` | `@read, @stream, @slow` |
| `xrange` | `stream` | `full` | `-` | `-4` | `-` | `no` | `@read, @stream, @slow` |
| `xread` | `stream` | `full` | `-` | `-4` | `-` | `no` | `@read, @stream, @slow, @blocking` |
| `xreadgroup` | `stream` | `full` | `-` | `-7` | `-` | `no` | `@write, @stream, @slow, @blocking` |
| `xrevrange` | `stream` | `full` | `-` | `-4` | `-` | `no` | `@read, @stream, @slow` |
| `xsetid` | `stream` | `full` | `-` | `-3` | `-` | `no` | `@write, @stream, @fast` |
| `xtrim` | `stream` | `full` | `-` | `-4` | `-` | `no` | `@write, @stream, @slow` |
| `zadd` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @fast` |
| `zcard` | `sorted-set` | `full` | `-` | `2` | `-` | `no` | `@read, @sortedset, @fast` |
| `zcount` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@read, @sortedset, @fast` |
| `zdiff` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @slow` |
| `zdiffstore` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zincrby` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@write, @sortedset, @fast` |
| `zinter` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @slow` |
| `zintercard` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @slow` |
| `zinterstore` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zlexcount` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@read, @sortedset, @fast` |
| `zmpop` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zmscore` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @fast` |
| `zpopmax` | `sorted-set` | `full` | `-` | `-2` | `-` | `no` | `@write, @sortedset, @fast` |
| `zpopmin` | `sorted-set` | `full` | `-` | `-2` | `-` | `no` | `@write, @sortedset, @fast` |
| `zrandmember` | `sorted-set` | `full` | `-` | `-2` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrange` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrangebylex` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrangebyscore` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrangestore` | `sorted-set` | `full` | `-` | `-5` | `-` | `no` | `@write, @sortedset, @slow` |
| `zrank` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @fast` |
| `zrem` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@write, @sortedset, @fast` |
| `zremrangebylex` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zremrangebyrank` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zremrangebyscore` | `sorted-set` | `full` | `-` | `4` | `-` | `no` | `@write, @sortedset, @slow` |
| `zrevrange` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrevrangebylex` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrevrangebyscore` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@read, @sortedset, @slow` |
| `zrevrank` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @fast` |
| `zscan` | `sorted-set` | `full` | `-` | `-3` | `-` | `yes` | `@read, @sortedset, @slow` |
| `zscore` | `sorted-set` | `full` | `-` | `3` | `-` | `no` | `@read, @sortedset, @fast` |
| `zunion` | `sorted-set` | `full` | `-` | `-3` | `-` | `no` | `@read, @sortedset, @slow` |
| `zunionstore` | `sorted-set` | `full` | `-` | `-4` | `-` | `no` | `@write, @sortedset, @slow` |
