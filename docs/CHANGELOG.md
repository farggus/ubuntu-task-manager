# Changelog

## [2.2.0](https://github.com/farggus/ubuntu-task-manager/compare/v2.1.0...v2.2.0) (2026-02-07)


### Features

* Add fails_before_ban tracking and caught slow brute-force display ([0db3364](https://github.com/farggus/ubuntu-task-manager/commit/0db33644ba713c01e3409859a518ebd54f3cdecf))
* Broadened slow brute-force detection (avg_interval &gt; findtime) ([e4845a7](https://github.com/farggus/ubuntu-task-manager/commit/e4845a7e241c043a6e59658ce3187a75c9986b9e))
* Phase 3 - Pattern detection and CAUGHT/EVADING logic ([a77cbb6](https://github.com/farggus/ubuntu-task-manager/commit/a77cbb66ede5da524e769dadef27868b87659123))
* **processes:** add column sorting and optimize performance ([612b6d0](https://github.com/farggus/ubuntu-task-manager/commit/612b6d03fa0ae2ad4e5648f2c74fb7837ea007a6))
* threats = slow brute-force with bans==0, EVADING = threats + 72h active ([c34e734](https://github.com/farggus/ubuntu-task-manager/commit/c34e73425cb4e8ef58a5e6a2d15ce8414aebe056))
* **ui:** graceful degradation for unavailable services ([052f761](https://github.com/farggus/ubuntu-task-manager/commit/052f7612aaa6b70005db0ecdc3a306531e24b574))


### Bug Fixes

* caught requires fails_before_ban &gt;= 10 ([6f93b8d](https://github.com/farggus/ubuntu-task-manager/commit/6f93b8d1868ff6c7991ffd1d78060f34ad2f7279))
* **f2b:** protect against None values in table refresh ([92b79b2](https://github.com/farggus/ubuntu-task-manager/commit/92b79b2883df35dd1d545d1319454df024eb986d))
* **logger:** add user-friendly error for log file permission denied ([5976da0](https://github.com/farggus/ubuntu-task-manager/commit/5976da0786dd8443ece43f8756b1ad885267c04c))
* **packages:** update package index before upgrade ([071be0d](https://github.com/farggus/ubuntu-task-manager/commit/071be0d12df364da9bbe36c87b7f3d4fbe868cc1))
* **processes:** add missing ProcessesTab import in deferred init ([89b4baa](https://github.com/farggus/ubuntu-task-manager/commit/89b4baa23f72197bae2fd3c332e59456efe45291))
* remove incorrect threat_detected=True for any banned IP ([f78c1bd](https://github.com/farggus/ubuntu-task-manager/commit/f78c1bdcf2f61f1ab92f8d25db4fcc62f0905150))
* **tests:** extract _do_export_snapshot for testability ([7835659](https://github.com/farggus/ubuntu-task-manager/commit/783565953d4a58f30bfe58682d829145ed89fea9))
* **tests:** prevent SMART background thread race conditions ([99ea77a](https://github.com/farggus/ubuntu-task-manager/commit/99ea77a1f0c5d2baec587640862f2ad84dc067dd))
* threats now counts only evasion_detected (matches SLOW jail) ([b5a8c80](https://github.com/farggus/ubuntu-task-manager/commit/b5a8c8062cd12b014ffeb010c51e2d4546d6a049))


### Performance Improvements

* **collectors:** shared process cache to avoid duplicate iteration ([04087ae](https://github.com/farggus/ubuntu-task-manager/commit/04087aeb4f042ce5b5fe12e1278b9c6e3e8c2d86)), closes [#13](https://github.com/farggus/ubuntu-task-manager/issues/13)
* **collectors:** single systemctl call in _get_service_stats() ([bf8886d](https://github.com/farggus/ubuntu-task-manager/commit/bf8886de7704eb154c86e49fd4d2f7cb9cc82f29))
* **dashboard:** non-blocking export_snapshot with [@work](https://github.com/work) ([530da43](https://github.com/farggus/ubuntu-task-manager/commit/530da43794b6fe24eb3e6aee6b932f6b3dbe6865))
* **dashboard:** refresh only active tab instead of all widgets ([f5e884f](https://github.com/farggus/ubuntu-task-manager/commit/f5e884fd96dd091b831908bcdd59caf3296d7f06))
* **logging:** quick preview + background full load ([c0782d9](https://github.com/farggus/ubuntu-task-manager/commit/c0782d9558d3ca4555e1b55a1ef191a0850f1823))
* **startup:** add detailed profiling and defer dashboard imports ([5ea5671](https://github.com/farggus/ubuntu-task-manager/commit/5ea5671b5f63a53855f84b02f7d69a356d7020bf))
* **startup:** defer Fail2ban+ data loading and reduce debug logging ([922ff28](https://github.com/farggus/ubuntu-task-manager/commit/922ff289feccad7ccad5459f1640c16c790dfd8b))
* **startup:** defer ProcessesTab creation to eliminate 600ms+ freeze ([2aee630](https://github.com/farggus/ubuntu-task-manager/commit/2aee63085739f82f9cd39a47d04ef691dfb9d7ef))
* **system:** non-blocking SMART collection with extended disk cache ([60c2020](https://github.com/farggus/ubuntu-task-manager/commit/60c2020e24753c10bc028a61fe5d0d8922a11a67))
* **system:** parallelize SystemCollector with background caching ([5002e09](https://github.com/farggus/ubuntu-task-manager/commit/5002e09893c120460f692b13bcbd8ad7f3954889))
* **ui:** defer initial data load to avoid blocking UI startup ([0953ae4](https://github.com/farggus/ubuntu-task-manager/commit/0953ae471caa4a73f00d289e3a62144bd45f0041))
* **ui:** implement progressive data rendering in System Information ([42c9c69](https://github.com/farggus/ubuntu-task-manager/commit/42c9c6973668db2884f1509ef720b66a430f03e4))
* **widgets:** lazy data loading with on_show instead of on_mount ([11df2cc](https://github.com/farggus/ubuntu-task-manager/commit/11df2cc87105381540e1399e6b975f72bcfb73ae))


### Documentation

* add SECURITY.md with vulnerability reporting policy ([20c62f5](https://github.com/farggus/ubuntu-task-manager/commit/20c62f529709aed5a63e5b0b882ae2abe3cba149))
* Update known issues documentation. ([d68cc55](https://github.com/farggus/ubuntu-task-manager/commit/d68cc55187e9ad51c1d63688faa2e24f20653419))
* update version to 2.1 and document lazy loading pattern ([a94d207](https://github.com/farggus/ubuntu-task-manager/commit/a94d2076b2d2273e4728bf4cfeea5d0f466247fc))

## [2.1.0](https://github.com/farggus/ubuntu-task-manager/compare/v2.0.0...v2.1.0) (2026-01-30)


### Features

* Add F2B Database Manager modal with [D] binding ([a8dbcc3](https://github.com/farggus/ubuntu-task-manager/commit/a8dbcc36902730d740ee2e080abf979b59ae3536))
* add Fail2ban dashboard tab with active, history, and slow brute-force views and management actions. ([ffe996e](https://github.com/farggus/ubuntu-task-manager/commit/ffe996ee9e9ddf97501a6f286b2a0b5f6ea325dd))
* add Fail2ban dashboard tab with active, history, and slow brute… ([78ef068](https://github.com/farggus/ubuntu-task-manager/commit/78ef0687f30599841ac19d785c410997da5f1a30))
* add Fail2ban dashboard tab with active, history, and slow detec… ([b587899](https://github.com/farggus/ubuntu-task-manager/commit/b587899976270f1ed7e55bfe867873f6badc4f36))
* add Fail2ban dashboard tab with active, history, and slow detector views, and IP management actions. ([43c958e](https://github.com/farggus/ubuntu-task-manager/commit/43c958e9c54e0828c94b83a5ed724d5e9ff48236))
* Add Fail2ban Slow Brute-Force Detection and Analysis ([22b28b6](https://github.com/farggus/ubuntu-task-manager/commit/22b28b6585108a481670155bfb8744df863a4f3d))
* Add Fail2banV2Collector log parser and update Fail2Ban+ tab ([278afb3](https://github.com/farggus/ubuntu-task-manager/commit/278afb3f6e4c3fb704f84c52f6e2154c883b9586))
* Add header to Fail2Ban+ tab populated from AttacksDatabase ([f6529b8](https://github.com/farggus/ubuntu-task-manager/commit/f6529b89678652987396cbb6c440ed4cfd07137b))
* Add unified AttacksDatabase and Fail2Ban+ tab ([f1c1055](https://github.com/farggus/ubuntu-task-manager/commit/f1c105596908e642e70a90eb53bdbb166ec72e08))
* AttacksDatabase Schema v2.0 ([c7c7246](https://github.com/farggus/ubuntu-task-manager/commit/c7c72463141e2dc0ba099edbec206ade1e7c9041))
* Auto-parse logs on F+ tab load, remove obsolete migrate_from_cache ([e22e4f4](https://github.com/farggus/ubuntu-task-manager/commit/e22e4f484baf6a47fbacb3bde9b089f3abf004a6))
* Filter out active banned IPs from Fail2ban history ([a085a23](https://github.com/farggus/ubuntu-task-manager/commit/a085a23810efd4b0fa1a40795d4db30a6d10262f))
* Header with identical format (jails, banned, unbanned, threats) from AttacksDatabase ([b2eb57e](https://github.com/farggus/ubuntu-task-manager/commit/b2eb57e820c2c2167185c8581ffd31693979bb1d))
* Hybrid header with Fail2banClient + AttacksDatabase ([915ef90](https://github.com/farggus/ubuntu-task-manager/commit/915ef9030c498526981e0ca8fe95c341c879d3c6))
* Sync active bans with fail2ban-client after log parsing ([49cfd6e](https://github.com/farggus/ubuntu-task-manager/commit/49cfd6e2a651f64dd2a1f466bd8e3eeed8dea67d))


### Bug Fixes

* Add show=True to binding, remove placeholder text ([ac59f32](https://github.com/farggus/ubuntu-task-manager/commit/ac59f32d4e100a8507802acbedeea4558de50292))
* Handle None log position in fail2ban_v2 parser ([3c1d379](https://github.com/farggus/ubuntu-task-manager/commit/3c1d379c6544fa050811f0232e6b9e7006a1582d))
* Initialize table columns in UsersTab on_mount ([d8d56a3](https://github.com/farggus/ubuntu-task-manager/commit/d8d56a3d5131884beb32f55d95793d416573bd31))
* Log position handling - make inode optional, extract position from dict ([bd56adb](https://github.com/farggus/ubuntu-task-manager/commit/bd56adb5c7a33c68b679dd0505ab3ed005ae9526))
* Make Fail2banPlusTab focusable for bindings to appear in footer ([eb2c30a](https://github.com/farggus/ubuntu-task-manager/commit/eb2c30a9e5d9b09859c224a2cf8929d6ed2f15ea))
* Remove auto-focus from Fail2banPlusTab ([8e1ca25](https://github.com/farggus/ubuntu-task-manager/commit/8e1ca2541472e8213e5a1062f5963f9954e7666b))
* Remove shell=True from subprocess in fail2ban.py ([d65d883](https://github.com/farggus/ubuntu-task-manager/commit/d65d883e1691547f0ff08ca1da5f043e9feb02b7))
* Sort imports in fail2ban_client.py ([85aee23](https://github.com/farggus/ubuntu-task-manager/commit/85aee23b5b82d2cfd562f7e5cb54513bf99024df))


### Performance Improvements

* Implement local caching for IP geolocation lookups ([c152c73](https://github.com/farggus/ubuntu-task-manager/commit/c152c733e270f5bb0b7006e44e7283ec913a1a1a))
* Increase unban history limit to 500 to show more historical data ([6e806f8](https://github.com/farggus/ubuntu-task-manager/commit/6e806f8ced568435f66c13e0c1883baab4e2ae4f))


### Documentation

* Add CONTRIBUTING.md ([3debf1e](https://github.com/farggus/ubuntu-task-manager/commit/3debf1ebbd37a1fe7b16e7176d405d6bbf61d1d8))
* Add GEMINI.md ([3ffb698](https://github.com/farggus/ubuntu-task-manager/commit/3ffb698cea593ca9e0935a831ca4b0f95d678d41))
* Add project audit reports and UI improvements ([d344f28](https://github.com/farggus/ubuntu-task-manager/commit/d344f285ded673454d718191dc7a7595d48ef4bb))
* enforce English language requirement for all project content- Translate logging_refactoring.md from to English- Add comprehensive Language Requirements section to CONTRIBUTING.md- Create docs/README.md with documentation guidelines and language policy- Establish English as mandatory language for:  * Code comments and docstrings  * Documentation files  * Commit messages and PR descriptions  * Log messages  * Variable/function names  * Issues and code reviewsThis ensures the project maintains international accessibility and professional standards as an open-source project.IMPORTANT: All future contributions must follow this language policy. ([3fa9609](https://github.com/farggus/ubuntu-task-manager/commit/3fa9609334a1e85d9acca822a767cdb7cc18e466))
* Remove an incorrect example comments from CONTRIBUTING.md. ([0dbd4fe](https://github.com/farggus/ubuntu-task-manager/commit/0dbd4fe0717a2fb3ab2eab455afc2e1879d418ee))
* Update AUDIT_FINAL.md with completed fixes ([621cb78](https://github.com/farggus/ubuntu-task-manager/commit/621cb782c8fb98e750b0c530ffbdeddcf831a7c6))

## v2.0.0 - Project Renamed to Ubuntu Task Manager (UTM) (2026-01-21)

### Major Changes
- **Project Rename**: Renamed from "HomeServer Inventory" to "Ubuntu Task Manager (UTM)".
- **Localization**: Entire codebase and documentation migrated to English.
- **Refactoring**: Codebase refactored to remove old naming conventions.

### Features
- **Process Management**: Monitor and manage system processes.
- **Service Control**: Start/Stop/Restart systemd services.
- **Container Management**: Docker container monitoring and logs.
- **Network Monitoring**: Interfaces, ports, and firewall rules.
- **Task Scheduling**: Cron jobs and systemd timers monitoring.

### Architecture
- Modular collector system.
- Textual-based TUI.
- Configuration via `config.yaml`.
