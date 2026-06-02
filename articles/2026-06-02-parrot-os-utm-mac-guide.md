---
title: "MacのUTMでParrotOSを動かしてみた（日本語入力・画面調整・共有フォルダも）"
emoji: "🦜"
type: "tech"
topics: ["utm", "mac", "parrotos", "linux", "virtualization"]
published: true
published_at: "2026-06-02 12:00"
---

## はじめに

セキュリティ学習用に **ParrotOS** を試してみたくて、Mac 上で動かす方法を探していました。UTM を使えば無料で仮想環境が作れると聞いたので、実際にやってみました。

インストール自体は意外と簡単でしたが、**日本語入力**・**画面サイズの自動調整**・**共有フォルダの設定**などは少し手間がかかったので、その辺りも含めてまとめておきます。

:::message
環境: MacBook Air M2 / UTM v4.x / ParrotOS Security 6.x（ARM64）
:::

---

## ParrotOS って何？

**ParrotOS**（Parrot Security OS）は Debian ベースのセキュリティ特化ディストリビューションです。KaliLinux と同系統ですが、動作が比較的軽量で、日常使いもできる Home エディションもあります。

セキュリティ学習・CTF・ペネトレーションテストの練習環境としてよく使われています。

---

## 1. 必要なものを準備する

### UTM のインストール

[https://mac.getutm.app](https://mac.getutm.app) から `.dmg` をダウンロードして、アプリケーションフォルダへドラッグするだけです。

Homebrew の場合:

```bash
brew install --cask utm
```

### ParrotOS ISO のダウンロード

[ParrotOS 公式サイト](https://parrotsec.org/download/) から ISO を取ってきます。

| エディション | 説明 |
|---|---|
| **Security** | ペネトレーションテストツール一式付き |
| **Home** | 軽量・日常利用向け |

:::message
**Apple Silicon（M1〜M4）** なら **ARM64版** を選ぶのがポイントです。ARM64版を使うと UTM の「仮想化」モードで動くので、x86版よりずっと速いです。

**Intel Mac** の場合は **amd64版** を選びます。
:::

---

## 2. 仮想マシンを作る

UTM を起動して「**+**」ボタンをクリックします。

**Apple Silicon の場合（ARM64 ISO）:**
→ 「**仮想化（Virtualize）**」を選択

**Intel Mac の場合（amd64 ISO）:**
→ 「**エミュレーション（Emulate）**」を選択

次に「Linux」を選び、ダウンロードした ISO ファイルを指定します。

### ハードウェア設定

| 項目 | 設定値 |
|---|---|
| メモリ | 4096 MB（4 GB）以上がおすすめ |
| CPU コア数 | 2〜4 |
| ストレージ | 30 GB 以上（Security なら 50 GB 推奨） |

VM に名前をつけて（例: `ParrotOS-Security`）保存すれば準備完了です。

---

## 3. ParrotOS をインストールする

▶ ボタンで VM を起動すると、起動メニューが出てきます。

**「Try / Install」** を選んでデスクトップを起動し、画面上の **「Install Parrot」** アイコンをダブルクリックするとインストーラーが始まります。

### 言語・地域の設定

インストーラーで日本語を選んでおくと、インストール後もシステムが日本語表示になります。（日本語**入力**は後で別途設定します）

### パーティション

「ディスク全体を使用」を選ぶのが一番楽です。

### ユーザーアカウントの作成

ユーザー名とパスワードを設定します。このパスワードがログインや `sudo` のパスワードになります。

### インストール完了後

インストールが終わったら再起動します。**このとき ISO を取り外し忘れると、再起動後にまたインストーラーが起動してしまう**ので注意です。

1. UTM で VM を右クリック → 「編集」
2. 「ドライブ」タブ → ISO のドライブを削除
3. VM を起動

---

## 4. まず最初にパッケージを更新する

ログインしたらターミナルを開いて更新しておきます。

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 5. 日本語入力を使えるようにする

デフォルトでは日本語が入力できないので、**Fcitx5 + Mozc** をインストールします。

### インストール

```bash
sudo apt install -y \
  fcitx5 \
  fcitx5-mozc \
  fcitx5-config-qt \
  fcitx5-frontend-gtk3 \
  fcitx5-frontend-gtk4 \
  fcitx5-frontend-qt5
```

### im-config で Fcitx5 を既定の IME に設定

```bash
im-config -n fcitx5
```

### 環境変数を設定する

`~/.profile`（または `~/.xprofile`）に以下を追加します。

```bash
echo 'export GTK_IM_MODULE=fcitx' >> ~/.profile
echo 'export QT_IM_MODULE=fcitx' >> ~/.profile
echo 'export XMODIFIERS=@im=fcitx' >> ~/.profile
```

### 自動起動の設定

MATE の「**システム → 設定 → スタートアップアプリケーション**」を開き、以下を追加します。

| 項目 | 値 |
|---|---|
| 名前 | Fcitx5 |
| コマンド | `fcitx5 -d` |

### 再起動して確認

```bash
reboot
```

再起動後、タスクバーに Fcitx5 のアイコンが出ていれば OK です。テキストエディタで `半角/全角` または `Ctrl + Space` を押して日本語入力に切り替わるか確認してみてください。

---

## 6. 画面サイズを自動調整できるようにする

デフォルトだとウィンドウのサイズを変えても VM の解像度が追従しません。**SPICE ゲストエージェント** を入れると自動調整が効くようになります。

### spice-vdagent をインストール

```bash
sudo apt install -y spice-vdagent
```

### UTM 側の設定

1. UTM で VM を右クリック → 「編集」
2. 「ディスプレイ」タブ → **「動的解像度」をオン**
3. VM を再起動

これで UTM のウィンドウサイズを変えると、ParrotOS の解像度が自動で変わるようになります。

:::message
この設定をすると、Mac と VM の間でのコピー＆ペーストも使えるようになります（クリップボード共有）。
:::

---

## 7. 共有フォルダ（Mac と VM でファイルを共有）

Mac 上のフォルダを ParrotOS から直接開けるようにします。

### UTM で共有フォルダを設定

1. UTM で VM を右クリック → 「編集」
2. **「共有」タブ** → 「共有ディレクトリ」に Mac のフォルダパスを設定
3. 保存して VM を再起動

### ParrotOS 側でマウントする

マウント先のディレクトリを作って、マウントします。

```bash
sudo mkdir -p /mnt/shared
sudo mount -t 9p -o trans=virtio share /mnt/shared -o version=9p2000.L
```

`ls /mnt/shared` でファイルが見えれば成功です。

### 起動時に自動マウントさせる

毎回手動でマウントするのは面倒なので、`/etc/fstab` に追記しておきます。

```bash
sudo nano /etc/fstab
```

末尾に追加:

```
share  /mnt/shared  9p  trans=virtio,version=9p2000.L,rw,_netdev,nofail  0  0
```

### 一般ユーザーで読み書きできるようにする

デフォルトだと root 所有になることがあるので、`uid` と `gid` を指定します。

```bash
# 自分の UID/GID を確認
id
```

fstab の行を以下のように変更します（`1000` は自分の uid/gid に合わせる）:

```
share  /mnt/shared  9p  trans=virtio,version=9p2000.L,rw,_netdev,nofail,uid=1000,gid=1000  0  0
```

再起動すると自動でマウントされます。

---

## 8. パスワードを変更する

### 自分のパスワードを変更

```bash
passwd
```

現在のパスワード → 新しいパスワード → 再入力の順で入力すれば完了です。

### root のパスワードを変更

```bash
sudo passwd root
```

### GUI から変更する

**「システム → 設定 → ユーザーとグループ」** からも変更できます。GUIのほうが直感的で簡単です。

---

## 9. ハマったポイントと対処法

### 起動時に「Boot failed」と出る

インストール後に ISO を取り外し忘れているケースが多いです。UTM の「編集 → ドライブ」で ISO を削除してから再起動してみてください。

### 解像度が変わらない

`systemctl status spice-vdagent` でサービスが動いているか確認します。UTM の「動的解像度」が ON になっているかも確認してください。

### 共有フォルダが見えない

`mount | grep 9p` でマウント状況を確認します。fstab の書き方を間違えているとマウントに失敗するので、まず手動マウントが動くか試してみるのがおすすめです。

### 日本語入力が効かない

```bash
# fcitx5 が起動しているか確認
ps aux | grep fcitx5

# 環境変数が設定されているか確認
echo $GTK_IM_MODULE
```

ログアウト → ログインし直すと解決することが多いです。

### Mac との間でコピー＆ペーストが効かない

`spice-vdagent` のインストールを忘れていないか確認してください。

---

## まとめ

UTM + ParrotOS の組み合わせは、想像以上に簡単に動きました。特に Apple Silicon Mac で ARM64 版を使うと動作がサクサクで快適です。

最初はデフォルト設定だと日本語入力や画面調整が使えないので少し戸惑いますが、この記事の手順をやれば問題なく使えるようになります。

セキュリティ学習やCTF練習の環境として、ぜひ試してみてください。

---

## 参考リンク

- [UTM 公式サイト](https://mac.getutm.app)
- [ParrotOS 公式サイト](https://parrotsec.org)
- [ParrotOS ドキュメント](https://parrotsec.org/docs/)
