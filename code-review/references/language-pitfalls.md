# 言語・技術別の着眼点

[観点チェックリスト](./checklist.md) を補う，言語や技術に固有の典型的な落とし穴．レビュー対象で使われているものの節だけを読む．ここにない言語や技術でも，同種の落とし穴（未定義動作，暗黙の型変換，資源の解放，非同期処理の誤用など）を確認する．挙動が言語やライブラリのバージョンによって異なる項目は，対象のプロジェクトが使うバージョンを確かめてから指摘する．

## 目次

- [C / C++](#c--c)
- [C#](#c)
- [Go](#go)
- [Java / Kotlin](#java--kotlin)
- [JavaScript / TypeScript](#javascript--typescript)
- [PHP](#php)
- [Python](#python)
- [Ruby](#ruby)
- [Rust](#rust)
- [シェルスクリプト](#シェルスクリプト)
- [SQL とマイグレーション](#sql-とマイグレーション)
- [CI/CD とインフラ定義](#cicd-とインフラ定義)

## C / C++

- 境界外アクセスとバッファオーバーフロー（配列の添字，`strcpy`，`strcat`，`sprintf`，`gets`，`memcpy` のサイズ計算）．`strncpy` は終端の NUL を保証しない．
- 整数のオーバーフロー（特にサイズ計算での乗算），`size_t` と `int` の混在，符号付きと符号なしの比較．符号付き整数のオーバーフローは未定義動作である．
- 未定義動作: 未初期化の変数，ヌルポインタの参照，strict aliasing 違反，ビット幅以上のシフト，評価順序に依存する式．
- メモリ管理: use-after-free，二重解放，リーク，`new[]` と `delete` の不一致，所有権の曖昧さ．RAII とスマートポインタ（`std::unique_ptr`）を使っているか．rule of zero/three/five．
- `p = realloc(p, n)` は失敗時に元の領域をリークする．
- 無効になったイテレータや参照の使用（`std::vector` への追加後，ループ中の `erase`）．
- ダングリング参照: ローカル変数への参照を返す，一時オブジェクトを指す `std::string_view` や `std::span`，参照でキャプチャしたラムダがスコープを越えて使われる．
- 例外安全性: デストラクタから例外を投げない．ムーブコンストラクタに `noexcept` がないと `std::vector` の再配置でコピーが使われる．
- データ競合は未定義動作である．`volatile` は同期の手段ではない．
- 書式文字列の脆弱性（`printf(user_input)`）．
- 戻り値の確認漏れ（`malloc`，`read`，`write` の部分書き込み，`fclose`）．
- シグナルハンドラ内での async-signal-safe でない関数の呼び出し．
- マクロの引数の多重評価や括弧の不足．
- 共有ライブラリの ABI 互換性（構造体のレイアウトの変更，ヘッダ内のインライン関数）．

## C#

- `async void`（イベントハンドラ以外），`.Result` や `.Wait()` による同期的な待機（同期コンテキスト上でのデッドロック），観測されないタスクの例外．ライブラリでの `ConfigureAwait(false)`．
- `IDisposable` を `using` で確実に破棄しているか．要求ごとに `HttpClient` を生成するとソケットが枯渇しうる（`IHttpClientFactory` か共有インスタンスを使う）．
- null 許容参照型の警告の無視や，`!` 演算子による抑制の乱用．
- LINQ: `IEnumerable` の多重列挙，遅延評価とキャプチャした変数，`First()` と `FirstOrDefault()` の使い分け．
- 文字列の比較と大文字小文字の変換でのカルチャ依存（`StringComparison.Ordinal`，トルコ語の i の問題）．
- `DateTime.Now` と `DateTime.UtcNow`，`DateTimeKind` の混在．
- `throw ex;` はスタックトレースを失う（`throw;` を使う）．
- EF Core: 遅延読み込みによる N+1，`FromSqlRaw` に文字列補間を渡すと SQL インジェクションになる（`FromSql` や `FromSqlInterpolated` を使う）．
- `lock(this)` や公開されたオブジェクト，文字列でのロック．
- 安全でないデシリアライズ（`BinaryFormatter`，Json.NET の `TypeNameHandling`）．

## Go

- エラーの無視（`_ =`，戻り値の確認漏れ），`errors.Is` と `errors.As` を使わない比較，`fmt.Errorf` での `%w` の付け忘れ．
- 型付きの nil ポインタを `error` インターフェースとして返すと，`err != nil` が真になる．
- `:=` による変数（特に `err`）のシャドーイング．
- goroutine のリーク（終了条件のない goroutine，受信者のいないチャネルへの送信），`context` のキャンセルの伝播，`defer cancel()` の付け忘れ．
- データ競合（`go test -race`）．map への並行した書き込みは実行時エラーで停止する．`sync.Mutex` を含む構造体のコピー（`go vet` の copylocks）．
- ループ変数のキャプチャ: `go.mod` の `go` ディレクティブが 1.22 未満なら，ループ変数は反復間で共有される．
- ループ内の `defer`（関数を抜けるまで資源が解放されない），`defer` の引数は登録時に評価される．
- スライスのエイリアシング（`append` が元の配列を共有して上書きする），小さな部分スライスによる大きな配列の保持．
- map の反復順序は不定である．
- `http.DefaultClient` や `http.Client{}` にはタイムアウトがない．`resp.Body.Close()` の呼び忘れ．
- `go.mod` の `go` ディレクティブが 1.23 未満なら，ループ内の `time.After` はタイマーが発火するまで解放されない．
- 整数の型変換によるオーバーフロー（`int` から `int32` など）．
- JSON: 非公開フィールドは扱われない，`omitempty` とゼロ値，未知のフィールドの扱い．
- モジュールのメジャーバージョンを上げるときのインポートパス（`/v2`）．

## Java / Kotlin

- `equals` と `hashCode` の契約．文字列やボクシングされた数値を `==` で比較していないか（`Integer` のキャッシュは -128〜127 のみ）．
- try-with-resources による資源の解放．
- NPE: `Optional` の誤用，Kotlin のプラットフォーム型と `!!`，Java との相互運用時の null 許容性．
- 並行性: `HashMap` の並行更新，スレッド安全でない `SimpleDateFormat`，`volatile` のないダブルチェックロッキング，反復中の変更による `ConcurrentModificationException`．
- `InterruptedException` を握りつぶさない（割り込み状態を復元するか，伝播させる）．`Exception` や `Throwable` の広すぎる捕捉．
- 信頼できないデータの Java シリアライズによるデシリアライズ．
- `BigDecimal`: `equals` はスケールも比較する（`compareTo` を使う）．`double` から生成すると誤差を含む（`BigDecimal.valueOf` か文字列から生成する）．
- XML パーサの既定設定による XXE（`DocumentBuilderFactory` など）．
- `java.util.Date` と既定のタイムゾーンへの依存（`java.time` を使う）．
- Spring: 同じクラス内からの呼び出しでは `@Transactional` が効かない．既定ではチェック例外でロールバックされない．
- JPA: N+1，セッション外での遅延読み込み．
- Kotlin コルーチン: `GlobalScope`，本番コードでの `runBlocking`，コルーチン内のブロッキング呼び出し，`CancellationException` の握りつぶし，構造化並行性からの逸脱．

## JavaScript / TypeScript

- `==` と `===`，真偽値への変換（`0`，`''`，`NaN`），既定値の `||` と `??` の違い．
- 非同期: `await` の付け忘れ，`forEach` に渡した async 関数は待たれない，未処理の Promise の拒否，`Promise.all` と `Promise.allSettled` の失敗時の違い，ループ内の逐次的な `await`．
- `this` の束縛（通常の関数とアロー関数）．
- 破壊的なメソッド（`sort`，`reverse`，`splice`）による共有配列の変更，スプレッド構文による浅いコピー．
- 数値: 浮動小数点数の誤差，`Number.MAX_SAFE_INTEGER` を超える整数（JSON の ID など），`parseInt` は不正な文字の手前で解析を打ち切る．
- `Date`: 月は 0 始まり．日付だけの文字列は UTC として，時差のない日時の文字列はローカル時刻として解釈される．
- `g` フラグ付きの正規表現は `lastIndex` を保持するため，`test()` を繰り返すと結果が変わる．破滅的なバックトラッキング．
- XSS: `innerHTML`，`dangerouslySetInnerHTML`，`v-html`，`javascript:` スキームの URL．
- プロトタイプ汚染（信頼できないオブジェクトのマージ，`__proto__`，`constructor`）．
- TypeScript: `any`，根拠のない `as` による型アサーション，非 null アサーション `!`，`@ts-ignore`．型は実行時に検証されないため，外部から受け取るデータはスキーマで検証する．判別可能な union の網羅性（`never` による確認）．
- Node.js: `child_process.exec` やシェル経由の実行への文字列の埋め込み（`execFile` や `spawn` に引数配列を渡す），利用者の入力を含むパスの `path.join`，要求処理中の同期 I/O，ストリームのエラー処理と背圧，イベントリスナーのリーク．
- React: フックのルール，依存配列の誤り（古いクロージャ），リストの `key` に添字を使う，状態の直接の変更，副作用の後始末．
- `dependencies` と `devDependencies` の区別，`postinstall` スクリプト，ESM と CommonJS の相互運用．

## PHP

- 緩い比較 `==` による型の相互変換（`"0e123" == "0e456"` は真）．`===` を使う．
- SQL インジェクション（プリペアドステートメントを使う）．
- XSS: `htmlspecialchars` に `ENT_QUOTES` と文字コードを指定しているか．
- 信頼できない入力の `unserialize`（オブジェクトインジェクション）．
- 利用者の入力によるファイルの `include` や `require`．
- パスワードは `password_hash` と `password_verify` で扱う．
- 本番環境でのエラーの画面表示（`display_errors`）．

## Python

- 可変オブジェクトを既定値にした引数（`def f(x=[])`）．
- ループ内で定義したクロージャの遅延束縛（ラムダがループ変数の最終値を参照する）．
- `is` と `==` の取り違え（数値や文字列のリテラルとの比較）．
- `except:` や `except Exception:` による握りつぶし．裸の `except:` は `KeyboardInterrupt` や `SystemExit` も捕捉する．
- `with` によるファイル，ロック，接続の解放．
- `/` と `//` の違い，浮動小数点数の誤差，`round()` は偶数丸め．
- `datetime` の naive と aware の混在．`datetime.utcnow()` は naive な値を返す（Python 3.12 で非推奨）．
- 反復中の辞書やリストの変更．ジェネレータやイテレータは一度しか走査できない．
- `subprocess` での `shell=True` と信頼できない入力，`os.system`．
- 信頼できないデータの `pickle`，`eval`，`exec`．PyYAML では `yaml.safe_load` を使う（`yaml.load` に `Loader=yaml.Loader` や `UnsafeLoader` を渡さない）．
- SQL を文字列の書式化で組み立てていないか（パラメータを使う）．
- `os.path.join` に絶対パスが渡されると，それ以前の要素が捨てられる．`tarfile.extractall` は Python 3.14 より前では既定で展開先の検証をしない（`filter="data"` を指定する）．
- asyncio: コルーチン内のブロッキング呼び出し，`await` されないコルーチン，`asyncio.create_task` の戻り値への参照を保持しないとタスクが途中で消えうる．
- GIL があっても複合操作は原子的ではない．
- Python 3.14 以前では，`encoding` を指定しない `open()` はロケールに依存した文字コードを使う．
- 検証に `assert` を使っている（`-O` で無効になる）．`__eq__` を定義して `__hash__` を定義していない．組み込み名（`list`，`id`，`type`）の上書き．
- インポート時の副作用，循環インポート．

## Ruby

- `send`，`public_send`，`constantize` に利用者の入力を渡していないか．
- Rails: Strong Parameters による一括代入の制限，`where("... #{value}")` のような文字列の埋め込みによる SQL インジェクション，`includes` を使わない N+1，バリデーションやコールバックを飛ばすメソッド（`update_all`，`update_column`）．
- `YAML.unsafe_load` や，Psych 4 未満での `YAML.load`（`YAML.safe_load` を使う）．
- `rescue Exception` や，何もしない `rescue`．
- 凍結された文字列リテラルの変更．
- クラス変数やクラスレベルのインスタンス変数のスレッド安全性．
- `||=` は値が `false` や `nil` の場合に再代入する．

## Rust

- ライブラリや要求処理の経路での `unwrap()`，`expect()`，添字アクセスによる panic．
- `unsafe` ブロック: 安全性の根拠（`// SAFETY:` コメント），健全性，別名規則，`Send` と `Sync` の手動実装．
- 整数のオーバーフローは，デバッグビルドでは panic し，リリースビルドでは（`overflow-checks` を有効にしない限り）折り返す．`as` による変換は黙って切り捨てられる（`try_from` を使う）．
- async: 非同期のコード内でのブロッキング呼び出し（`std::thread::sleep`，同期 I/O），`std::sync::Mutex` のガードを `.await` をまたいで保持すること．
- `Rc` の循環参照によるリーク，`mem::forget`，`Drop` の順序への依存．
- エラー処理: `?` による変換で文脈が失われる，ライブラリの公開 API での `Box<dyn Error>` や `anyhow` の使用．
- 公開 API の互換性: `#[non_exhaustive]` のない列挙型へのバリアントの追加，トレイトの変更．
- feature フラグは加算的であるべきで，組み合わせによってビルドが壊れないか．
- アトミック変数での `Ordering::Relaxed` の誤用．

## シェルスクリプト

- 変数をクォートしていない（単語分割とパス名展開）．`"$@"` と `$*` の違い．
- `set -euo pipefail` の有無と落とし穴．`set -e` は `if` や `&&`，`||` の中，`pipefail` なしのパイプラインでは効かない．`local var=$(cmd)` は `cmd` の終了ステータスを隠す．
- `cd` の失敗を確認しているか（`cd dir || exit 1`）．
- `rm -rf "$DIR/"` で `DIR` が空や未定義だった場合の挙動（`${DIR:?}` を使う）．
- 一時ファイルは `mktemp` で作り，`trap` で削除する．
- `eval` や，信頼できない入力のコマンドへの埋め込み．
- `for f in $(ls)` は空白や改行を含むファイル名で壊れる（`find -print0` と `xargs -0` などを使う）．`read` に `-r` を付ける．
- shebang と使っている構文の一致（`bash` の機能を `/bin/sh` で使っていないか）．`echo -e` の移植性（`printf` を使う）．
- ShellCheck の指摘を確認する．

## SQL とマイグレーション

- パラメータ化されていないクエリ．
- `NULL` の三値論理（`= NULL`，`NOT IN` の対象に `NULL` が含まれると結果が空になる）．
- インデックスを使えない条件（列への関数の適用，前方一致でない `LIKE`，暗黙の型変換）．
- トランザクションの境界，分離レベル，行ロック（`SELECT ... FOR UPDATE`），デッドロック．
- `WHERE` のない，または誤った `UPDATE` と `DELETE`．
- `ORDER BY` のないページング（順序が不定），大きな `OFFSET` の性能．
- 大きなテーブルを長時間ロックする DDL（DB とバージョンによっては，列の追加やインデックスの作成がテーブルをロックする．PostgreSQL では `CREATE INDEX CONCURRENTLY` を検討する）．
- NOT NULL 列の追加とバックフィル，ロールバックの手順，新旧のアプリケーションが混在する期間の互換性（列の削除や名前の変更は段階的に行う）．
- 文字コードと照合順序，タイムゾーン付きの日時型，金額に浮動小数点型を使わない．

## CI/CD とインフラ定義

- GitHub Actions:
  - `pull_request_target` や `workflow_run` で，フォークからの PR のコードをチェックアウトして実行していないか．
  - `${{ github.event.* }}` などの外部から制御できる値を `run:` に直接埋め込んでいないか（スクリプトインジェクション．環境変数を経由させる）．
  - `permissions:` が最小限か．サードパーティのアクションをコミット SHA で固定しているか．秘密情報がログやフォークの PR に渡らないか．
- Dockerfile: ベースイメージのタグの固定（`latest` を避ける），root での実行，`ARG`・`ENV`・`COPY` による秘密情報のレイヤーへの混入，`.dockerignore` の欠如，パッケージのキャッシュの削除，マルチステージビルド．
- Kubernetes: リソースの requests と limits，`securityContext`（`runAsNonRoot`，`readOnlyRootFilesystem`，`privileged`），liveness と readiness のプローブ，ConfigMap に置かれた秘密情報，イメージのタグの固定．
- Terraform などの IaC: 公開されたストレージや `0.0.0.0/0` を許可するセキュリティグループ，ワイルドカードを含む IAM ポリシー，秘密情報を含む state ファイル，再作成（replace）によるデータの消失，`prevent_destroy`，プロバイダのバージョンの固定．
