---
title: "MacでUTMを使ってParrotOSをインストールする完全ガイド"
emoji: "🦜"
type: "tech"
topics: ["utm", "mac", "parrotos", "linux", "virtualization"]
published: true
published_at: "2026-06-02 12:00"
---

## はじめに

**ParrotOS**（Parrot Security OS）はセキュリティ調査・ペネトレーションテスト・プライバシー保護を目的としたDebian系Linuxディストリビューションです。KaliLinuxと並んでセキュリティ学習に広く使われており、動作が比較的軽量なのが特徴です。

この記事では、**Mac（Apple Silicon / Intel）上でUTMを使ってParrotOSを仮想マシンとして動かす方法**を、以下のトピックを含めて解説します。

1. UTM・ParrotOS ISOの準備
2. 仮想マシンの作成・インストール
3. **日本語入力の設定**
4. **画面サイズの自動調整**
5. **共有フォルダ（ShareFolder）の設定**
6. **パスワードの変更**

:::message
本記事は **UTM v4.x** と **ParrotOS 6.x（MATE デスクトップ）** をもとに作成しています。バージョンによってUI・操作が異なる場合があります。
:::

---

## 1. 事前準備

### 1-1. UTM のインストール

[https://mac.getutm.app](https://mac.getutm.app) から `.dmg` をダウンロードし、アプリケーションフォルダへドラッグします。

Homebrew を使う場合:

```bash
brew install --cask utm
```

### 1-2. ParrotOS ISO のダウンロード

[ParrotOS 公式サイト](https://parrotsec.org/download/) から ISO をダウンロードします。

| エディション | 説明 | 推奨用途 |
|---|---|---|
| **Security** | ペネトレーションテストツール一式付き | セキュリティ学習・CTF |
| **Home** | 軽量・日常利用向け | プライバシー重視の普段使い |

:::message
**Apple Silicon（M1/M2/M3/M4）** をお使いの場合は **ARM64版** を選んでください。UTM の「仮想化」モードで高速に動作します。x86_64版を選ぶと「エミュレーション」モードになり速度が大幅に低下します。

**Intel Mac** の場合は通常の **amd64版** を選択します。
:::

ARM64版のファイル名例:
```
Parrot-security-6.x_arm64.iso
Parrot-home-6.x_arm64.iso
```

---

## 2. UTM で仮想マシンを作成する

### 2-1. 新規 VM の作成

UTM を起動し、**「+」ボタン** をクリックします。

**Apple Silicon Mac（ARM64 ISO を使う場合）:**
→ **「仮想化（Virtualize）」** を選択

**Intel Mac（amd64 ISO を使う場合）:**
→ **「エミュレーション（Emulate）」** を選択

### 2-2. OS の選択

「Linux」を選択し、「次へ」をクリックします。

### 2-3. ブートイメージの指定

「参照」ボタンからダウンロードした ParrotOS の ISO ファイルを選択します。

### 2-4. ハードウェア設定

| 項目 | 推奨値 |
|---|---|
| **メモリ** | 4096 MB（4 GB）以上 |
| **CPU コア数** | 2〜4 |

ParrotOS Security は多くのツールが含まれるため、最低でも **4 GB のメモリ** を割り当てることを推奨します。

### 2-5. ストレージ設定

最低 **30 GB**、Security エディションを使う場合は **50 GB 以上** を推奨します。

### 2-6. 共有フォルダ（後で設定する場合はスキップ可）

Mac 上のフォルダを VM と共有したい場合はここで指定できます。後から設定することも可能です。

### 2-7. 名前の設定と保存

VM 名を入力（例: `ParrotOS-Security`）して「保存」をクリックします。

---

## 3. ParrotOS のインストール

### 3-1. VM の起動

VM を選択して ▶ **「再生」** ボタンをクリックします。

### 3-2. インストーラーの起動

起動メニューが表示されたら **「Try / Install」** を選択します。

デスクトップが起動したら、画面上の **「Install Parrot」** アイコンをダブルクリックしてインストーラーを起動します。

### 3-3. 言語・地域の設定

| 項目 | 設定値 |
|---|---|
| 言語 | Japanese（または English） |
| 地域 | Japan |
| キーボード | Japanese |

:::message
インストーラーで日本語を選択しておくと、システムが日本語UIで起動します。ただし日本語**入力**（IME）は別途設定が必要です（後述）。
:::

### 3-4. パーティション設定

「ディスク全体を使用」を選択するのが最も簡単です。仮想ディスクを丸ごと ParrotOS に割り当てます。

### 3-5. ユーザーアカウントの作成

| 項目 | 説明 |
|---|---|
| フルネーム | 表示名（例: `Parrot User`） |
| ユーザー名 | ログイン名（例: `user`） |
| パスワード | ログイン・sudo に使用するパスワード |

:::message alert
**パスワードは必ず設定してください。** 後から変更する方法は [セクション 7](#7-パスワードの変更) で解説します。
:::

### 3-6. インストール完了

インストールが完了したら「今すぐ再起動」をクリックします。

**ISO の取り出し（重要）:**
再起動前または再起動後に ISO を取り出さないと、再度インストーラーが起動してしまいます。

1. UTM の VM リストで対象 VM を **右クリック → 「編集」**
2. 「ドライブ」タブ → ISO のドライブを選択 → 「削除」
3. VM を起動

---

## 4. 初期セットアップ（パッケージ更新）

インストール直後にパッケージを最新にしておきます。

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 5. 日本語入力の設定

ParrotOS（MATE デスクトップ）で日本語入力を使うには、**Fcitx5 + Mozc** の組み合わせが安定しています。

### 5-1. Fcitx5 と Mozc のインストール

```bash
sudo apt install -y \
  fcitx5 \
  fcitx5-mozc \
  fcitx5-config-qt \
  fcitx5-frontend-gtk3 \
  fcitx5-frontend-gtk4 \
  fcitx5-frontend-qt5
```

### 5-2. im-config で Fcitx5 を既定の IME に設定

```bash
im-config -n fcitx5
```

### 5-3. 環境変数の設定

`~/.profile` または `~/.xprofile` に以下を追記します。

```bash
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
```

```bash
# .profile に追記する場合
echo 'export GTK_IM_MODULE=fcitx' >> ~/.profile
echo 'export QT_IM_MODULE=fcitx' >> ~/.profile
echo 'export XMODIFIERS=@im=fcitx' >> ~/.profile
```

### 5-4. 自動起動の設定

MATE のセッション起動時に Fcitx5 が立ち上がるよう設定します。

**「システム」→「設定」→「スタートアップアプリケーション」** を開き、「追加」をクリックします。

| 項目 | 値 |
|---|---|
| 名前 | Fcitx5 |
| コマンド | `fcitx5 -d` |

### 5-5. 再起動・動作確認

```bash
reboot
```

再起動後、タスクバーに Fcitx5 のアイコンが表示されます。テキストエディタを開いて `半角/全角` キーまたは `Ctrl + Space` で日本語入力に切り替えられれば成功です。

### 5-6. Fcitx5 の入力メソッド設定

タスクバーの Fcitx5 アイコンを右クリック → 「設定」を開き、**「入力メソッド」** に「Mozc」が追加されていることを確認します。

なければ「+」ボタンから「Mozc」を追加してください。

---

## 6. 画面サイズの自動調整

UTM のウィンドウサイズに合わせて VM の解像度を自動調整するには、**SPICE ゲストエージェント** を使います。

### 6-1. spice-vdagent のインストール

```bash
sudo apt install -y spice-vdagent
```

### 6-2. UTM の「動的解像度」を有効化

1. UTM の VM リストで対象 VM を **右クリック → 「編集」**
2. 「ディスプレイ」タブを開く
3. **「動的解像度（Dynamic Resolution）」** をオンにする
4. VM を再起動

### 6-3. 動作確認

VM ウィンドウの端をドラッグしてサイズを変えると、ParrotOS の画面解像度が自動的に追従して変わります。

:::message
SPICE エージェントはクリップボードの共有（Mac ↔ VM 間でのコピー＆ペースト）も有効にします。非常に便利な機能です。
:::

---

## 7. 共有フォルダ（Share Folder）の設定

Mac 上のフォルダを ParrotOS から直接アクセスできるように設定します。UTM は **VirtFS（9P プロトコル）** を使って共有します。

### 7-1. UTM で共有フォルダを設定

1. UTM の VM リストで対象 VM を **右クリック → 「編集」**
2. **「共有」** タブを開く
3. 「共有ディレクトリ」に Mac 側のフォルダパスを入力（または「参照」で選択）
4. 設定を保存して VM を再起動

### 7-2. ParrotOS 側でマウントポイントを作成

```bash
sudo mkdir -p /mnt/shared
```

### 7-3. 手動マウント（動作確認）

```bash
sudo mount -t 9p -o trans=virtio share /mnt/shared -o version=9p2000.L
```

マウント後にファイルが見えることを確認します。

```bash
ls /mnt/shared
```

### 7-4. 起動時に自動マウント（/etc/fstab）

毎回手動でマウントするのは手間なので、`/etc/fstab` に追記して自動マウントにします。

```bash
sudo nano /etc/fstab
```

末尾に以下を追加します:

```
share  /mnt/shared  9p  trans=virtio,version=9p2000.L,rw,_netdev,nofail  0  0
```

保存して再起動すると、起動時に自動でマウントされます。

```bash
sudo reboot
```

再起動後に確認:

```bash
ls /mnt/shared
```

### 7-5. 一般ユーザーでのアクセス権設定

デフォルトでは root のみアクセス可能な場合があります。一般ユーザーでも読み書きできるようにするには、fstab のオプションに `uid` と `gid` を追加します。

```bash
# 自分のUID/GIDを確認
id
# uid=1000(user) gid=1000(user) ...
```

fstab を以下のように編集します（`uid=1000,gid=1000` の部分は自分の値に合わせる）:

```
share  /mnt/shared  9p  trans=virtio,version=9p2000.L,rw,_netdev,nofail,uid=1000,gid=1000  0  0
```

---

## 8. パスワードの変更

### 8-1. 現在のユーザーのパスワードを変更

ターミナルを開いて以下を実行します:

```bash
passwd
```

```
現在のパスワード: （現在のパスワードを入力）
新しいパスワード: （新しいパスワードを入力）
新しいパスワードを再入力してください: （新しいパスワードを再入力）
passwd: パスワードは正しく更新されました
```

### 8-2. root パスワードを変更

```bash
sudo passwd root
```

:::message alert
ParrotOS はデフォルトで root ログインを制限しています。通常の操作は `sudo` を使い、root パスワードの変更は必要な場合のみ行いましょう。
:::

### 8-3. 別のユーザーのパスワードを変更（管理者権限が必要）

```bash
sudo passwd <ユーザー名>
```

### 8-4. GUI でパスワードを変更（MATE）

**「システム」→「設定」→「ユーザーとグループ」** からも変更できます。

---

## 9. よくあるトラブル

### Q. 起動時に「Boot failed」と表示される

- ISO が正しく設定されているか確認（インストール後は ISO を取り外す）
- 「編集」→「UEFI ブート」の ON/OFF を切り替えてみる
- ARM64 ISO を使っているのに「エミュレーション」を選んでいないか確認

### Q. 解像度が変わらない

- `spice-vdagent` がインストールされているか確認: `systemctl status spice-vdagent`
- UTM の「動的解像度」が ON になっているか確認
- VM を再起動する

### Q. 共有フォルダが見えない

- UTM の「共有」タブでフォルダが設定されているか確認
- `mount | grep 9p` でマウント状況を確認
- `_netdev` オプションを外してみる（ネットワーク依存の問題）

### Q. 日本語入力が効かない

- `fcitx5 -d &` をターミナルで実行し、fcitx5 が起動しているか確認
- `echo $GTK_IM_MODULE` で `fcitx` と表示されるか確認
- ログアウト → ログインし直す

### Q. Mac との間でコピー＆ペーストが効かない

- `spice-vdagent` をインストールする
- `systemctl --user status spice-vdagent` でサービス起動状態を確認

### Q. マウスが VM の中に閉じ込められた

`Control + Option` キーでマウスを解放できます。

---

## 10. まとめ

| やること | コマンド / 手順 |
|---|---|
| パッケージ更新 | `sudo apt update && sudo apt upgrade -y` |
| 日本語入力インストール | `sudo apt install fcitx5 fcitx5-mozc` |
| IME 設定 | `im-config -n fcitx5` → 環境変数設定 → 再起動 |
| 画面自動調整 | `sudo apt install spice-vdagent` → UTM「動的解像度」ON |
| 共有フォルダ設定 | UTM「共有」タブ → `/etc/fstab` に追記 |
| パスワード変更 | `passwd` |

UTM + ParrotOS の組み合わせは、Mac 上でセキュリティ学習環境を手軽に構築するのに最適です。スナップショット機能（[UTM スナップショットガイド](./2026-05-16-utm-mac-guide)）も活用して、実験前後で安全に状態を保存・復元しながら学習を進めましょう。

---

## 参考リンク

- [UTM 公式サイト](https://mac.getutm.app)
- [ParrotOS 公式サイト](https://parrotsec.org)
- [ParrotOS ドキュメント](https://parrotsec.org/docs/)
- [Fcitx5 Wiki](https://fcitx-im.org/wiki/Fcitx_5)
