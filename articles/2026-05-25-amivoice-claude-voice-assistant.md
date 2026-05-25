---
title: "AmiVoice API × Claude APIで作るリアルタイム日本語音声対話システム"
emoji: "🎙️"
type: "tech"
topics: ["amivoice", "claude", "音声認識", "生成AI", "nodejs"]
published: true
published_at: "2026-05-25 09:00"
---

# AmiVoice API × Claude APIで作るリアルタイム日本語音声対話システム

## はじめに

「日本語の音声認識を使ったAIアシスタントを作りたい」と思ったとき、真っ先に悩むのが精度です。汎用の音声認識エンジンでは、専門用語や日本語特有の表現がうまく認識されないことが多く、生成AIへの入力品質が落ちてしまいます。

本記事では、日本語特化の音声認識API「**AmiVoice API**」と「**Claude API**」を組み合わせ、高精度な日本語音声対話システムを構築する方法を解説します。WebSocketを使ったストリーミング認識により、話し終わる前から認識が始まる快適な体験を実現します。

### 完成するシステムの概要

- ブラウザのマイクから音声を取得
- AmiVoice APIのWebSocketで**リアルタイムストリーミング認識**
- 認識テキストをClaude APIに渡して**自然な応答を生成**
- Server-Sent Events（SSE）で応答を**ストリーミング表示**

![システム構成図](https://storage.googleapis.com/zenn-user-upload/placeholder.png)
*ブラウザ → Node.jsサーバー → AmiVoice API / Claude API*

---

## AmiVoice APIとは

[AmiVoice API](https://acp.amivoice.com/)は株式会社アドバンスト・メディアが提供する日本語特化の音声認識クラウドサービスです。

### 特徴

| 機能 | 内容 |
|------|------|
| 日本語精度 | 医療・法律・金融など専門領域モデルあり |
| インターフェース | REST API / WebSocket API |
| ストリーミング | WebSocket経由でリアルタイム認識可能 |
| 話者分離 | 複数話者の発言を分離できるオプションあり |
| 無料枠 | 月60分の無料利用が可能（2026年5月時点） |

汎用エンジンと比べ、日本語固有表現・固有名詞・専門用語の認識精度が高く、AIへの入力品質向上に直結します。

---

## システム構成

```
[ブラウザ]
  │  Web Audio API でマイク音声取得（PCM 16kHz）
  │  WebSocket でサーバーへ送信
  ▼
[Node.js サーバー]
  │  ブラウザ ↔ AmiVoice を中継する WebSocket プロキシ
  │  認識確定テキストを受け取り Claude API へ転送
  │  SSE でクライアントへストリーミング返答
  ▼
[AmiVoice API]     [Claude API]
  音声認識           応答生成
```

### 技術スタック

- **バックエンド**: Node.js 20 + Express + `ws`ライブラリ
- **フロントエンド**: バニラJS（フレームワークなし）
- **音声認識**: AmiVoice API（WebSocketストリーミング）
- **生成AI**: Claude claude-sonnet-4-6（claude-sonnet-4-6）

---

## 実装

### 1. 環境準備

```bash
mkdir voice-assistant && cd voice-assistant
npm init -y
npm install express ws @anthropic-ai/sdk dotenv
```

`.env`ファイルを作成します。

```env
AMIVOICE_APP_KEY=your_amivoice_app_key
ANTHROPIC_API_KEY=your_anthropic_api_key
PORT=3000
```

AmiVoice APIキーは[ACP（Advanced Media Cloud Platform）](https://acp.amivoice.com/)のコンソールから取得できます。

### 2. サーバー実装（`server.js`）

```javascript
import express from 'express';
import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import Anthropic from '@anthropic-ai/sdk';
import 'dotenv/config';

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server, path: '/ws' });

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// 会話履歴（セッションごとに管理）
const sessions = new Map();

// AmiVoice WebSocket エンドポイント
const AMIVOICE_WS_URL = 'wss://acp-api.amivoice.com/v1/websocket';

wss.on('connection', (clientWs) => {
  const sessionId = crypto.randomUUID();
  sessions.set(sessionId, { history: [], amiWs: null });

  console.log(`[${sessionId}] Client connected`);

  // AmiVoice への接続を確立
  const amiWs = new WebSocket(AMIVOICE_WS_URL);
  sessions.get(sessionId).amiWs = amiWs;

  amiWs.on('open', () => {
    // 認識設定を送信（grammarFileNames で認識エンジンを選択）
    const config = [
      'S',                          // コマンド: Start
      `-a ${process.env.AMIVOICE_APP_KEY}`,
      '-e utf-8',
      '-l 16k',                     // サンプリングレート 16kHz
      '-g -a-general',              // 汎用日本語モデル
    ].join(' ');

    amiWs.send(config);
    console.log(`[${sessionId}] AmiVoice connected`);
  });

  // AmiVoice からの認識結果を処理
  amiWs.on('message', async (data) => {
    const text = data.toString();

    // 'U' = 確定テキスト, 'S' = 途中テキスト
    if (text.startsWith('U\t')) {
      const utterance = text.split('\t').slice(2).join('\t').trim();
      if (!utterance) return;

      console.log(`[${sessionId}] Recognized: ${utterance}`);

      // 認識テキストをクライアントに通知
      clientWs.send(JSON.stringify({ type: 'recognized', text: utterance }));

      // Claude で応答生成
      await generateResponse(sessionId, utterance, clientWs);
    } else if (text.startsWith('S\t')) {
      // 途中認識テキストをリアルタイムで表示
      const partial = text.split('\t').slice(2).join('\t').trim();
      if (partial) {
        clientWs.send(JSON.stringify({ type: 'partial', text: partial }));
      }
    }
  });

  amiWs.on('error', (err) => {
    console.error(`[${sessionId}] AmiVoice error:`, err.message);
    clientWs.send(JSON.stringify({ type: 'error', message: 'AmiVoice connection error' }));
  });

  // クライアントからの音声データを AmiVoice に中継
  clientWs.on('message', (data) => {
    if (amiWs.readyState === WebSocket.OPEN) {
      if (typeof data === 'string') {
        // テキストコマンド（開始/停止）
        const msg = JSON.parse(data);
        if (msg.type === 'start') {
          amiWs.send('p');  // 音声入力開始
        } else if (msg.type === 'stop') {
          amiWs.send('e');  // 音声入力終了
        }
      } else {
        // バイナリ音声データをそのまま転送
        amiWs.send(data);
      }
    }
  });

  clientWs.on('close', () => {
    console.log(`[${sessionId}] Client disconnected`);
    if (amiWs.readyState === WebSocket.OPEN) {
      amiWs.close();
    }
    sessions.delete(sessionId);
  });
});

// Claude API で応答をストリーミング生成
async function generateResponse(sessionId, userText, clientWs) {
  const session = sessions.get(sessionId);
  if (!session) return;

  // 会話履歴に追加
  session.history.push({ role: 'user', content: userText });

  // 履歴が長くなりすぎないよう最新20件に制限
  if (session.history.length > 20) {
    session.history = session.history.slice(-20);
  }

  clientWs.send(JSON.stringify({ type: 'ai_start' }));

  let fullResponse = '';

  try {
    const stream = await anthropic.messages.stream({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      system: `あなたは親切な音声アシスタントです。
ユーザーの質問に簡潔かつ丁寧に日本語で答えてください。
音声で読み上げることを前提に、箇条書きや記号は避け、
自然な話し言葉で回答してください。`,
      messages: session.history,
    });

    for await (const chunk of stream) {
      if (
        chunk.type === 'content_block_delta' &&
        chunk.delta.type === 'text_delta'
      ) {
        const token = chunk.delta.text;
        fullResponse += token;
        clientWs.send(JSON.stringify({ type: 'ai_token', text: token }));
      }
    }

    // アシスタントの応答を履歴に追加
    session.history.push({ role: 'assistant', content: fullResponse });
    clientWs.send(JSON.stringify({ type: 'ai_end' }));
  } catch (err) {
    console.error(`[${sessionId}] Claude error:`, err.message);
    clientWs.send(JSON.stringify({ type: 'error', message: 'AI response error' }));
  }
}

app.use(express.static('public'));

server.listen(process.env.PORT, () => {
  console.log(`Server running at http://localhost:${process.env.PORT}`);
});
```

### 3. フロントエンド実装（`public/index.html`）

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>音声対話アシスタント</title>
  <style>
    body { font-family: sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; }
    #status { color: #666; font-size: 0.9em; margin-bottom: 8px; }
    #transcript { min-height: 40px; padding: 12px; background: #f5f5f5; border-radius: 8px; color: #333; }
    #response { min-height: 80px; padding: 12px; margin-top: 12px; background: #e8f4fd; border-radius: 8px; }
    button { padding: 12px 32px; font-size: 1rem; border-radius: 8px; border: none; cursor: pointer; margin-top: 16px; }
    #btn-start { background: #4CAF50; color: white; }
    #btn-stop  { background: #f44336; color: white; display: none; }
    .partial { color: #999; font-style: italic; }
  </style>
</head>
<body>
  <h1>🎙️ 音声対話アシスタント</h1>
  <div id="status">待機中...</div>
  <div id="transcript">（ここに認識テキストが表示されます）</div>
  <div id="response">（ここにAIの返答が表示されます）</div>
  <button id="btn-start">録音開始</button>
  <button id="btn-stop">録音停止</button>

  <script>
    const ws = new WebSocket(`ws://${location.host}/ws`);
    const statusEl = document.getElementById('status');
    const transcriptEl = document.getElementById('transcript');
    const responseEl = document.getElementById('response');
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');

    let audioContext, mediaStream, processor;

    // WebSocket メッセージ処理
    ws.onmessage = ({ data }) => {
      const msg = JSON.parse(data);
      switch (msg.type) {
        case 'partial':
          transcriptEl.innerHTML = `<span class="partial">${msg.text}...</span>`;
          break;
        case 'recognized':
          transcriptEl.textContent = msg.text;
          responseEl.textContent = '考え中...';
          break;
        case 'ai_start':
          responseEl.textContent = '';
          break;
        case 'ai_token':
          responseEl.textContent += msg.text;
          break;
        case 'ai_end':
          statusEl.textContent = '録音中... 話しかけてください';
          break;
        case 'error':
          statusEl.textContent = `エラー: ${msg.message}`;
          break;
      }
    };

    // 録音開始
    btnStart.addEventListener('click', async () => {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new AudioContext({ sampleRate: 16000 });

      const source = audioContext.createMediaStreamSource(mediaStream);

      // ScriptProcessorNode で PCM データを取得（最新環境では AudioWorklet 推奨）
      processor = audioContext.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        const float32 = e.inputBuffer.getChannelData(0);
        const int16 = convertToInt16(float32);
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(int16.buffer);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      ws.send(JSON.stringify({ type: 'start' }));

      btnStart.style.display = 'none';
      btnStop.style.display = 'inline-block';
      statusEl.textContent = '録音中... 話しかけてください';
    });

    // 録音停止
    btnStop.addEventListener('click', () => {
      ws.send(JSON.stringify({ type: 'stop' }));
      processor?.disconnect();
      mediaStream?.getTracks().forEach(t => t.stop());
      audioContext?.close();

      btnStop.style.display = 'none';
      btnStart.style.display = 'inline-block';
      statusEl.textContent = '待機中...';
    });

    // Float32 → Int16 変換（WebAudio API → PCM 変換）
    function convertToInt16(float32Array) {
      const int16 = new Int16Array(float32Array.length);
      for (let i = 0; i < float32Array.length; i++) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      return int16;
    }
  </script>
</body>
</html>
```

### 4. 実行

```bash
node --env-file=.env server.js
# → http://localhost:3000 をブラウザで開く
```

---

## 実装のポイント

### AmiVoice WebSocket プロトコルの注意点

AmiVoiceのWebSocketプロトコルはやや独特で、最初につまずきやすい点が3つあります。

**1. 接続コマンドのフォーマット**

接続後に最初に送るのはJSONではなくスペース区切りの文字列です。

```
S -a {APP_KEY} -e utf-8 -l 16k -g -a-general
```

`S` はセッション開始コマンドで、`-g` オプションの後に使用する音声認識エンジン（文法ファイル）を指定します。

**2. 音声データ送信タイミング**

設定コマンドを送った後、`p`（recognition start）コマンドを送ってから音声バイナリを流します。順序を誤ると認識が動きません。

```
接続 → Sコマンド（設定）→ pコマンド（開始）→ 音声バイナリ → eコマンド（終了）
```

**3. 認識結果のパース**

認識結果はタブ区切りのテキストで返ってきます。

```
U\t{セグメントID}\t{認識テキスト}\t{信頼度}\t...
```

`U`が確定テキスト、`S`が途中結果です。2番目以降のタブ区切りフィールドが認識テキストになります。

### 会話の質を高める Claude のシステムプロンプト設計

音声対話では、テキストチャットとは異なる制約があります。

```javascript
system: `あなたは親切な音声アシスタントです。
ユーザーの質問に簡潔かつ丁寧に日本語で答えてください。
音声で読み上げることを前提に、箇条書きや記号は避け、
自然な話し言葉で回答してください。`
```

**避けるべき表現**:
- 「・」「-」などの箇条書き記号 → TTS（Text-to-Speech）で変な読まれ方をする
- コードブロック → 音声では意味をなさない
- 「①②③」などの番号記号 → 「まるいち」と読まれることがある

**推奨する表現**:
- 「まず〜、次に〜、最後に〜」などの接続詞で列挙
- 「〜ですね。〜ということになります。」のような自然な口語

### レイテンシを下げる工夫

ストリーミング認識と応答生成を組み合わせると、体感レイテンシを大幅に削減できます。

```
[音声入力]
  ↓ 約200ms（AmiVoice途中認識）
[中間テキスト表示]
  ↓ 確定まで待つ
[Claude API呼び出し]
  ↓ 約300ms（初回トークン）
[応答ストリーミング表示開始]
```

ユーザーの発話が終わってからClaude APIを呼ぶため、合計レイテンシは概ね1〜2秒程度です。さらに高速化したい場合は、途中認識テキスト（`S`コマンドの結果）をトリガーにして先行してClaude APIを呼び出す「投機的応答生成」も有効です。

---

## 専門領域モデルへの切り替え

AmiVoiceの強みは専門用語認識です。`-g`オプションのエンジンを変えるだけで対応領域を切り替えられます。

```javascript
// 医療現場向け
'-g -a-medgeneral'

// 金融・ビジネス向け
'-g -a-bizfinance'

// コールセンター向け（電話音声）
'-g -a-callcenter'
```

例えば医療記録システムでは、「右季肋部痛（うみぎろくぶつう）」「狭心症（きょうしんしょう）」などが正確に認識されます。これを生成AIに渡すと、電子カルテの下書き生成や医療コードの提案など、専門的なアシストが可能になります。

---

## 発展的なアイデア

本記事の構成を応用すると、以下のようなシステムに発展できます。

### 議事録自動生成システム

話者分離オプション（`-S`）を使うと、複数人の発言を分けて認識できます。これをClaudeに渡せば「誰が何を言ったか」を含む構造化された議事録を自動生成できます。

```javascript
// 話者分離を有効化
const config = `S -a ${APP_KEY} -e utf-8 -l 16k -g -a-general -S 2`;
//                                                              ↑ 話者数（最大指定）
```

### カスタムボキャブラリーとの組み合わせ

AmiVoiceはユーザー辞書（カスタムボキャブラリー）登録をサポートしています。社内固有の製品名やプロジェクト名を登録することで、認識精度をさらに高められます。

```bash
# カスタムボキャブラリー登録（REST API）
curl -X POST https://acp-api.amivoice.com/v1/vocabularyRegistrations \
  -H "Authorization: Bearer ${APP_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"words": [{"displayString": "プロジェクトフェニックス"}]}'
```

### Web Speech API とのフォールバック

AmiVoice APIが利用できない環境向けに、ブラウザ標準の`SpeechRecognition`（Web Speech API）をフォールバックとして実装しておくと、可用性が上がります。

```javascript
const recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const useAmiVoice = !!process.env.AMIVOICE_APP_KEY;
```

---

## まとめ

AmiVoice APIとClaude APIを組み合わせることで、次の効果が得られました。

| 課題 | 解決策 |
|------|--------|
| 日本語専門用語の誤認識 | AmiVoice専門領域モデル |
| 応答の不自然さ（箇条書き等）| 音声向けシステムプロンプト |
| レイテンシの長さ | WebSocketストリーミング + SSE |
| 会話の文脈喪失 | サーバー側の会話履歴管理 |

特に医療・法律・金融など専門用語が多い領域で、汎用エンジンからAmiVoiceへの乗り換え効果は大きく、生成AIへの入力品質が向上することで最終的な応答品質も改善します。

音声インターフェースはキーボードに比べて直感的で、ハンズフリー操作を必要とする現場（工場、医療、物流）で特に有効です。本記事の実装をベースに、ぜひ自分のユースケースに合わせたカスタマイズを試してみてください。

---

## 参考リンク

- [AmiVoice API ドキュメント](https://docs.amivoice.com/amivoice-api/)
- [Anthropic Claude API リファレンス](https://docs.anthropic.com/en/api/getting-started)
- [Web Audio API - MDN](https://developer.mozilla.org/ja/docs/Web/API/Web_Audio_API)
