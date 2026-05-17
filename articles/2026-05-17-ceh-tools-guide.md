---
title: "CEH試験対策：ハッキングツールを5フェーズで完全整理"
emoji: "🛠️"
type: "tech"
topics: ["security", "ceh", "pentest", "ethical-hacking", "tools"]
published: true
published_at: "2026-05-17 09:00"
---

## はじめに

CEH（Certified Ethical Hacker）試験では、**攻撃の各フェーズで使われるツールの名前・用途・動作原理**が頻出です。「どのフェーズで何を使うか」を体系的に押さえることが、試験合格と実務双方での近道になります。

この記事では、CEH の **攻撃5フェーズ** と **主要ドメイン** に沿って、代表的なツールを一覧で整理します。

:::message alert
本記事は学習・研究目的のまとめです。記載ツールの無断使用は違法になる場合があります。必ず適切な許可を得た環境でのみ使用してください。
:::

---

## CEH 攻撃5フェーズ とツールの対応

```
Phase 1: Reconnaissance（偵察）        ← 情報収集
Phase 2: Scanning（スキャン）           ← ポート・脆弱性調査
Phase 3: Gaining Access（侵入）         ← エクスプロイト
Phase 4: Maintaining Access（維持）     ← バックドア・持続化
Phase 5: Covering Tracks（痕跡消去）    ← ログ削除・隠蔽
```

---

## Phase 1: Reconnaissance（偵察）

### パッシブ偵察（対象に触れない）

| ツール | 用途 | 特徴 |
|---|---|---|
| **Maltego** | OSINT・関係マッピング | グラフUIで人・ドメイン・IP の関係を可視化 |
| **Shodan** | インターネット公開機器の検索 | バナー情報・サービス・脆弱バージョンを検索 |
| **theHarvester** | メール・ドメイン・サブドメイン収集 | Google/Bing/LinkedIn など複数ソースを自動クロール |
| **Recon-ng** | OSINT フレームワーク | Metasploit ライクなモジュール構成 |
| **FOCA** | メタデータ抽出 | PDF/Word ファイルからメタデータ（作成者・パスなど）を取得 |
| **Censys** | Shodan の代替・証明書情報も取得 | TLS 証明書経由でのサブドメイン列挙に有効 |
| **SpiderFoot** | 自動 OSINT | メール・IP・ドメイン・SNS を横断収集 |

### アクティブ偵察（対象に接触する）

| ツール | 用途 | 特徴 |
|---|---|---|
| **Nslookup / Dig** | DNS 照会 | A/MX/NS/AAAA/PTR レコードの確認 |
| **Whois** | ドメイン登録情報取得 | 登録者・ネームサーバー・有効期限を確認 |
| **Traceroute / Tracert** | 経路追跡 | パケットの経路と RTT をホップごとに確認 |
| **Netcraft** | Web サーバー情報調査 | OS・Webサーバーの種類とバージョンを取得 |

---

## Phase 2: Scanning（スキャン）

### ポートスキャン

| ツール | 用途 | 特徴 |
|---|---|---|
| **Nmap** | ポート・サービス・OS スキャン | CEH最重要ツール。TCP/UDP/SYN/Xmas など多彩なスキャン方式 |
| **Zenmap** | Nmap の GUI フロントエンド | Nmap コマンドを視覚的に操作・可視化 |
| **Angry IP Scanner** | 軽量ネットワークスキャナ | IP レンジを高速にスキャン |
| **Masscan** | 超高速ポートスキャナ | インターネット全体を数分でスキャン可能 |
| **Unicornscan** | 非同期ポートスキャナ | UDP スキャンにも強い |

### Nmap 主要フラグ早見表

| フラグ | スキャン種別 | 説明 |
|---|---|---|
| `-sS` | SYN Scan（Stealth） | 接続を完了させずにポートを検出（最もよく使われる） |
| `-sT` | TCP Connect Scan | 完全接続（ログに残りやすい） |
| `-sU` | UDP Scan | UDP ポートのスキャン |
| `-sX` | Xmas Scan | FIN+PSH+URG フラグを立てる |
| `-sN` | Null Scan | フラグをすべてオフにする |
| `-sF` | FIN Scan | FIN フラグのみ |
| `-O` | OS Detection | TTL などからOSを推定 |
| `-sV` | Service Version | サービスのバージョンを取得 |
| `-A` | Aggressive | OS+Version+Script+Traceroute |
| `-p-` | 全ポートスキャン | 65535 ポート全てを対象にする |

### 脆弱性スキャン

| ツール | 用途 | 特徴 |
|---|---|---|
| **Nessus** | 脆弱性スキャナ | 業界標準。CVSS スコアで重大度を分類 |
| **OpenVAS** | OSS 脆弱性スキャナ | Nessus の代替オープンソース版 |
| **Nexpose** | Rapid7 製脆弱性管理 | Metasploit と連携可能 |
| **Qualys** | クラウド型脆弱性管理 | エージェントレス・SaaS で提供 |
| **Retina** | eEye 製スキャナ | パッチ管理機能付き |

### 列挙（Enumeration）

| ツール | 用途 | 特徴 |
|---|---|---|
| **Enum4linux** | SMB/NetBIOS 列挙 | ユーザー・共有・グループ情報を取得 |
| **NBTscan** | NetBIOS スキャン | NetBIOS 名前テーブルを収集 |
| **SNMPwalk** | SNMP 列挙 | MIB ツリーを再帰的に取得 |
| **ldapsearch** | LDAP 列挙 | Active Directory のユーザー・OU 情報を取得 |
| **Gobuster / Dirbuster** | Web ディレクトリ列挙 | ワードリストで隠しパスを総当たり |
| **wfuzz** | Web ファジング | パラメータ・パス・ヘッダーのファジング |

---

## Phase 3: Gaining Access（侵入）

### エクスプロイトフレームワーク

| ツール | 用途 | 特徴 |
|---|---|---|
| **Metasploit Framework** | エクスプロイト・ペイロード実行 | CEH最重要ツール。2000超のモジュールを内蔵 |
| **BeEF (Browser Exploitation Framework)** | ブラウザ経由の攻撃 | XSS でフックしブラウザを制御 |
| **Exploit-DB / searchsploit** | エクスプロイトデータベース | CVE に対応するエクスプロイトコードを検索 |

#### Metasploit 主要コマンド

```bash
msfconsole             # 起動
search <keyword>       # モジュール検索
use <module>           # モジュール選択
show options           # オプション一覧
set RHOSTS <target>    # ターゲット設定
set PAYLOAD <payload>  # ペイロード選択
run / exploit          # 実行
sessions -l            # セッション一覧
sessions -i <id>       # セッションに接続
```

### パスワードクラック

| ツール | 手法 | 特徴 |
|---|---|---|
| **Hashcat** | オフラインクラック（GPU） | 世界最速。MD5/NTLM/bcrypt など多数のハッシュ対応 |
| **John the Ripper** | オフラインクラック | ルールベース攻撃が強力。Unix Shadow ファイルに強い |
| **Hydra** | オンライン総当たり | SSH/FTP/HTTP/RDP/SMB など50以上のプロトコル対応 |
| **Medusa** | オンライン総当たり | Hydra の代替。並列処理が高速 |
| **Aircrack-ng** | Wi-Fi ハンドシェイククラック | WPA/WPA2 の 4-way ハンドシェイクを解析 |
| **CeWL** | カスタムワードリスト生成 | ターゲットサイトをクロールして単語帳を生成 |
| **Crunch** | ワードリスト生成 | 文字種・長さを指定してリスト生成 |

#### パスワード攻撃の種類

| 攻撃種別 | 説明 |
|---|---|
| **Dictionary Attack** | 既知の単語リストを使用 |
| **Brute Force** | 全組み合わせを試行 |
| **Rule-based Attack** | 変換ルール（leet 置換など）を適用 |
| **Rainbow Table** | 事前計算済みハッシュテーブルと比較 |
| **Pass-the-Hash (PtH)** | ハッシュそのものを認証に使用（Windowsネットワーク） |

### ソーシャルエンジニアリング

| ツール | 用途 | 特徴 |
|---|---|---|
| **SET (Social-Engineer Toolkit)** | フィッシング・クローンサイト | 最も使われる SE フレームワーク |
| **Gophish** | フィッシングキャンペーン管理 | WebUI でメール送信・追跡が可能 |
| **King Phisher** | フィッシングメール送信 | SMTP 設定が柔軟 |

### Webアプリケーション攻撃

| ツール | 用途 | 特徴 |
|---|---|---|
| **Burp Suite** | Web プロキシ・脆弱性診断 | CEH頻出。インターセプト・リピーター・スキャナ機能 |
| **OWASP ZAP** | OSS Web スキャナ | Burp Suite の OSS 代替 |
| **SQLmap** | SQL インジェクション自動化 | DB の種類を自動判別し盲目的なSQLiも検出 |
| **Nikto** | Web サーバースキャナ | 既知の脆弱設定・ファイルを自動検出 |
| **w3af** | Web アプリケーションフレームワーク | 200以上のプラグインで診断 |
| **XSStrike** | XSS 検出・エクスプロイト | コンテキストを分析して高精度のペイロード生成 |

### ワイヤレス攻撃

| ツール | 用途 | 特徴 |
|---|---|---|
| **Aircrack-ng スイート** | Wi-Fi 攻撃の総合ツール | Monitor mode → Capture → Crack の一連を担う |
| **Airodump-ng** | パケットキャプチャ | BSSID・ESSID・CH・クライアントを一覧化 |
| **Aireplay-ng** | パケットインジェクション | Deauth 攻撃でハンドシェイクを強制取得 |
| **Kismet** | 無線LAN 探索・モニタリング | 隠しSSID の検出も可能 |
| **Wifite** | Wi-Fi 自動攻撃 | WEP/WPA/WPS を自動で試行 |
| **Fern Wifi Cracker** | GUI Wi-Fi クラッカー | Aircrack-ng をGUIで操作 |

#### WPA2 クラックの概念フロー（試験で問われるステップ）

CEH 試験では「どのツールがどのステップを担うか」が問われます。

| ステップ | 役割 | 使用ツール |
|---|---|---|
| ① モニターモード有効化 | 通常の通信を傍受可能な状態にする | `airmon-ng` |
| ② AP・クライアント探索 | 対象ネットワークの BSSID/CH を特定 | `airodump-ng` |
| ③ ハンドシェイクキャプチャ | 4-way ハンドシェイクをファイルに保存 | `airodump-ng` |
| ④ 再接続誘発（オプション） | クライアントを切断して再接続させる | `aireplay-ng` |
| ⑤ オフラインクラック | キャプチャしたハンドシェイクにワードリストを照合 | `aircrack-ng` / `hashcat` |

**防御側の視点：** WPA3 への移行、強力なパスフレーズ（20文字以上）の使用、Deauth フレームを検知する WIDS（無線侵入検知システム）の導入が対策として有効です。

---

## Phase 4: Maintaining Access（持続化）

| ツール | 用途 | 特徴 |
|---|---|---|
| **Meterpreter** | 高機能リモートシェル | Metasploit のペイロード。メモリ常駐・ファイルレス |
| **Netcat (nc)** | リバースシェル・バインドシェル | ネットワークの「スイスアーミーナイフ」 |
| **Cobalt Strike** | C2（Command & Control）フレームワーク | 商用APTシミュレーションツール |
| **Empire** | PowerShell C2 フレームワーク | エージェントレスでの Windows 権限昇格 |
| **Pupy** | クロスプラットフォーム RAT | Python ベース・メモリ内実行 |
| **Weevely** | PHP ウェブシェル | ターゲットWebサーバーへのバックドア |

### 権限昇格（Privilege Escalation）

| ツール | 用途 | 特徴 |
|---|---|---|
| **LinPEAS / WinPEAS** | 権限昇格のチェック自動化 | SUID/Cron/設定ミスなど数百の確認点を自動スキャン |
| **PowerSploit** | PowerShell 攻撃フレームワーク | `Invoke-Mimikatz` など強力なモジュール群 |
| **Mimikatz** | Windows 認証情報抽出 | LSASS から平文パスワード・NTLM ハッシュを取得 |
| **BeRoot** | Linux/Windows 権限昇格チェック | sudo ミス・PATH ハイジャックなどを検出 |

---

## Phase 5: Covering Tracks（痕跡消去）と防御

このフェーズでは、攻撃者が「何を狙って消そうとするか」を理解し、**それを守る防御策**を対応付けて覚えるのが CEH の本来の目的です。

### 攻撃者が標的にするログ・痕跡と防御策

| 攻撃者の標的 | 使われる手法 | 防御策・SOC での検知ポイント |
|---|---|---|
| **Windows イベントログ** | ログのクリア・監査ポリシー無効化 | Event ID 1102（ログクリア）・Event ID 4719（監査ポリシー変更）をアラート設定 |
| **ファイルのタイムスタンプ** | タイムスタンプ改ざん（Timestomp） | ファイル整合性監視（FIM）ツールでハッシュ変化を検知 |
| **syslog / auth.log** | 特定 IP のエントリ削除 | ログをリモートの集中 SIEM にリアルタイム転送して改ざんを無効化 |
| **ファイル痕跡** | 上書き削除（shred など） | 削除イベントの監視・バックアップによる復元 |
| **通信の隠蔽** | ステガノグラフィ（画像内への埋め込み） | DLP・コンテンツ検査による異常なバイナリ構造の検出 |

### 防御の基本原則（試験頻出）

| 原則 | 内容 |
|---|---|
| **ログの集中管理** | ローカルログは改ざんされうる。SIEM にリアルタイム転送し不変性を確保する |
| **監査ポリシーの保護** | 監査ポリシー変更自体をログ・アラート対象にする |
| **FIM（ファイル整合性監視）** | 重要ファイルのハッシュを定期比較し改ざんを検知する |
| **最小権限の原則** | ログ削除・監査設定変更は管理者権限を要する。権限の最小化で被害範囲を限定する |

---

## ネットワーク盗聴・MITM

| ツール | 用途 | 特徴 |
|---|---|---|
| **Wireshark** | パケット解析 | GUI でキャプチャ・フィルタリング・解析 |
| **tcpdump** | CLI パケットキャプチャ | スクリプトや自動化に向く |
| **Ettercap** | ARP スプーフィング・MITM | LAN 内の通信を傍受・改ざん |
| **Bettercap** | Ettercap の後継 MITM ツール | HTTPS も含めた傍受。モジュラー設計 |
| **Responder** | LLMNR/NBT-NS 毒化 | Windows 環境のハッシュキャプチャに有効 |
| **MITMf** | MITM フレームワーク | SSLstrip・DNS スプーフィングなど統合 |
| **Arpspoof** | ARP テーブル汚染 | dsniff スイートの一部 |

---

## IDS/ファイアウォール回避

| ツール / 手法 | 用途 | 特徴 |
|---|---|---|
| **Nmap フラグ操作** | デコイスキャン・断片化 | `-D RND:10`（デコイ）`-f`（断片化）`-T0`（遅延） |
| **Proxychains** | プロキシ経由で接続 | Tor や SOCKS プロキシを連鎖させる |
| **Tor** | 匿名通信 | オニオンルーティングで送信元を隠蔽 |
| **VPN / SSH トンネル** | 暗号化トンネル | IDS がパケット内容を読めなくする |
| **Veil Framework** | ペイロード難読化 | AV 検知を回避する Meterpreter ペイロード生成 |
| **Shellter** | PE ファイル注入 | 既存の Windows EXE にシェルコードを埋め込む |

---

## フォレンジック・ステガノグラフィ

| ツール | 用途 | 特徴 |
|---|---|---|
| **Autopsy** | デジタルフォレンジック | The Sleuth Kit のGUIフロントエンド |
| **FTK (Forensic Toolkit)** | 商用フォレンジックスイート | AccessData 製。証拠収集・解析・レポート |
| **Volatility** | メモリフォレンジック | メモリダンプからプロセス・ネットワーク・パスワードを解析 |
| **dd / dcfldd** | ビット単位ディスクコピー | フォレンジックイメージ取得 |
| **Steghide** | ステガノグラフィ埋め込み・抽出 | JPEG/BMP/WAV に情報を隠蔽 |
| **Stegdetect** | ステガノグラフィ検出 | 統計解析でステガノグラフィの存在を推定 |
| **ExifTool** | メタデータ確認・編集 | 画像・ドキュメントのメタデータ全般に対応 |

---

## DoS/DDoS ツール

:::message alert
DoS/DDoS 攻撃ツールは**許可を得た環境以外での使用は違法**です。CEH試験では概念・防御の観点から出題されます。
:::

| ツール | 攻撃種別 | 特徴 |
|---|---|---|
| **LOIC (Low Orbit Ion Cannon)** | UDP/TCP/HTTP フラッド | 匿名化なし・シンプルな負荷生成 |
| **HOIC (High Orbit Ion Cannon)** | HTTP フラッド | スクリプト可能・分散攻撃向け |
| **hping3** | カスタムパケット送信 | SYN フラッド・スマーフ攻撃の検証に使用 |
| **Slowloris** | 低速HTTP攻撃 | 少ないリソースでWebサーバーを枯渇させる |
| **R.U.D.Y.** | HTTP POST 低速攻撃 | ボディを極めてゆっくり送信しスレッドを占有 |

---

## CEH 試験対策：ツール問題の解き方

### 問われがちなパターン

1. **用途を問う** — 「Nessus は何のためのツールか？」
2. **フェーズを問う** — 「Covering Tracks に使うツールはどれか？」
3. **コマンドを問う** — 「Nmap で SYN スキャンするフラグは？」
4. **ツールの組み合わせ** — 「Wi-Fi クラックの正しい手順はどれか？」

### 必須暗記ツール（頻出度★★★）

| 優先度 | ツール | 理由 |
|---|---|---|
| ★★★ | Nmap | 全ドメインで使われる・フラグ問題が頻出 |
| ★★★ | Metasploit | 侵入フェーズの代名詞 |
| ★★★ | Wireshark | スニッフィング・解析の定番 |
| ★★★ | Burp Suite | Webアプリ診断の標準ツール |
| ★★★ | Aircrack-ng | 無線LAN 攻撃の全ステップをカバー |
| ★★☆ | Hashcat / John | パスワードクラック |
| ★★☆ | Hydra | オンライン総当たりの定番 |
| ★★☆ | Nessus | 脆弱性スキャン |
| ★★☆ | Maltego | OSINT・偵察の可視化 |
| ★★☆ | SET | ソーシャルエンジニアリング |

---

## ツール分類の早見表

| カテゴリ | 代表ツール |
|---|---|
| OSINT | Maltego, theHarvester, Recon-ng, Shodan |
| ポートスキャン | Nmap, Masscan, Angry IP Scanner |
| 脆弱性スキャン | Nessus, OpenVAS, Nexpose |
| 列挙 | Enum4linux, Gobuster, SNMPwalk |
| エクスプロイト | Metasploit, Exploit-DB |
| パスワードクラック | Hashcat, John, Hydra, Aircrack-ng |
| Webアプリ | Burp Suite, SQLmap, Nikto, ZAP |
| ソーシャルエンジニアリング | SET, Gophish |
| 無線LAN | Aircrack-ng, Kismet, Wifite |
| スニッフィング/MITM | Wireshark, Ettercap, Bettercap, Responder |
| 持続化/RAT | Netcat, Meterpreter, Cobalt Strike |
| 権限昇格 | Mimikatz, LinPEAS, PowerSploit |
| IDS 回避 | Proxychains, Veil, Tor |
| フォレンジック | Autopsy, Volatility, FTK |
| ステガノグラフィ | Steghide, Stegdetect |
| DoS | LOIC, hping3, Slowloris |

---

## まとめ

CEH のツール問題は「**どのフェーズで**・**何の目的で**・**どのツールを使うか**」を問うパターンが中心です。

- **Nmap, Metasploit, Wireshark, Burp Suite, Aircrack-ng** の5ツールを最優先で深く理解する
- 各ツールの主要コマンドとフラグも暗記しておく
- ツールが「攻撃5フェーズのどこに位置するか」をマッピングしておくと応用が利く

この記事が CEH の試験合格と実践的なセキュリティスキル習得に役立てば幸いです。

---

## 参考

- [EC-Council 公式 CEH ページ](https://www.eccouncil.org/train-certify/certified-ethical-hacker-ceh/)
- [Nmap 公式ドキュメント](https://nmap.org/book/man.html)
- [Metasploit Unleashed](https://www.offensive-security.com/metasploit-unleashed/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
