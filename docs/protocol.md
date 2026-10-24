# SmartLAN/G local web protocol (reverse engineered)

Everything below comes from browser captures (HAR) of the panel's own web UI
(SmartLiving 515 + SmartLAN/G). Items marked **?** are not verified.

* Endpoint: `POST http://HOST:PORT/cgi-bin/web.cgi`, `application/x-www-form-urlencoded`, plain HTTP.
* Login: `user`, `pass`, `mod=auth`, `code` -> HTML `<div id='msg_content' qindex='..' tk='..'>ACK</div>`.
  The body must be exactly `ACK`. The token `tk` was observed to be **static**: unchanged after
  a day, after re-login and across devices (probably derived from the credentials). Treat it like a password.
* Every other call: `tk`, `qindex`, `mod`, optional `par`, `act`. Replies are JSON.
* `GET /sw_str_panel` ("6.01 00515"-style: firmware + model code) and `GET /version.html`, unauthenticated.

| mod | par / act | reply |
|---|---|---|
| `sce` | - | `{"sce":[{lb,id,..}]}` all arming scenarios |
| `sce` | `par=now` | `{lb,id}` current scenario |
| `do_sce` | `par=<scenario id>` | `{"do_sce":"<id>"}` |
| `part` | - | `{"part":[{lb,am,st,mm,id}]}`; am 1 away,2 stay,3 instant,4 disarm,5 reset; mm alarm memory |
| `do_part` | `par=<partition id>`, `act=<am code>` | |
| `zone` | none (discovery) then `par=<mask>` | `{"zone":[{lb,st,mm,by,tl,id}]}`; `id` zone number, `tl` compact index |
| `cmd` | - | `{"cmd":[{lb,st,id,t,..}]}` outputs; `t` type (0 on/off, others slider/dimmer) **?**; `tl` compact index. Listed only for a **user** code: with the installer code the list is empty |
| `do_zone` | `par=<zone id>`, `act=0/1` | web UI buttons: ON -> `act=0`, OFF -> `act=1`; zone field `by`=1 shows the "valid" icon (included). Mapping to exclude/include **?** |
| `do_cmd` | `par=<output id>`, `act=1/0` | |
| `tmr` | - | `{"tmr":[{lb,st,id}]}` read-only timers; meaning of `st` **?** (all 0 when idle) |
| `fau` | - | `{"fau":<bitmask>,"vcc":"13,8"}` see `FAULT_BITS` in `const.py` |
| `gsm` | - | `vcc, fwv, gop, gpw, cre` ("--" = n/a) |
| `log` | `par=<n lines, max 500>` | `{"log":[{id,dt,ty,ag,lo,al}]}` ascending ids, `dt` is DD/MM/YYYY HH:MM:SS panel time (zone unknown **?**), `ty` event text, `ag` user, `lo` place, `al` partitions `[{id,lb}]`; `par=1` returning only the latest entry **?** |
| `nrzs` / `nrza` | scenario id / partition id (+act) | `{"nrz":[{lb}]}` zones not ready before arming; the web UI calls it before arming (`nrza`: `act` = arm code - 1 for codes 1-3, disarm/reset skip it; `nrzs`: `act=0`) and refuses to arm if the list is not empty; skipped when firmware major < 5 |

Mask for `zone`: 7 hex words of 8 digits, comma separated, bit = `tl` (word `tl // 32`, bit `tl % 32` - word>0 **?**).
Status codes (from the UI icons, **?**): zone st 1 rest / 0 fault / 2 alarm / 3 short; partition st 1 rest / 0 alarm / 2 fault / 3 short.
Panel firmware dated 2014 sends a malformed header order that strict HTTP clients reject (reported by another user).

## Android app transport (observed in a PCAPdroid capture, not decoded)

The official Android app does **not** use `web.cgi`. It talks to the panel on **TCP port 5004**
(same port locally and through the router) and also resolves an INIM cloud hostname.
Payloads are binary, always multiples of 16 bytes (block cipher, **?** AES). The same request
produced byte-identical replies on two separate connections, so there is no per-session IV/nonce
or session key. Seen so far: 16 B client -> 16 B panel reply -> 16 B client -> 192 B panel reply.
Without the key nothing can be read, and it is not needed: outputs are available from the web
protocol (`mod=cmd`) when logging in with a user code.
