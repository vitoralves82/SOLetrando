# SOLetrando 🎙️

<p align="center">
  <img src="icon_idle.png" alt="SOLetrando" width="128">
</p>

Ditado e leitura por voz para *Windows*, gratuitos e executados no próprio computador, com [faster-whisper](https://github.com/SYSTRAN/faster-whisper) em GPU NVIDIA ou CPU.

Pressione **Scroll Lock**, fale e pressione de novo: o texto aparece onde estiver o cursor (Word, navegador, bloco de notas, qualquer programa). Selecione um texto e pressione **Ctrl+Alt+A** para ouvi-lo em voz alta.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![CUDA](https://img.shields.io/badge/CUDA-opcional-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

> **[English version below](#english)**

---

## Funcionalidades

- **Processamento local:** o áudio e o texto são processados no computador. A internet é usada para baixar o modelo de reconhecimento na primeira vez.
- **Ditado com prévia:** uma caixa flutuante mostra o texto enquanto você fala; o resultado final é inserido de uma vez no campo de destino.
- **Leitura em voz alta** do texto selecionado em qualquer programa, com a voz do *Windows* que você escolher, velocidade ajustável e atalho próprio.
- **Vocabulário e correções pessoais** para nomes, siglas e termos recorrentes.
- **Último ditado e histórico local** para recuperar um texto depois.
- **Privacidade configurável:** o registro técnico não guarda vocabulário nem correções, e o ditado pode ficar fora do histórico da área de transferência do *Windows* (Win+V).
- **Todas as preferências numa janela** (clique no ícone da bandeja), além do menu de clique direito.
- **Ícone na bandeja** com cores de estado: amarelo = pronto, azul = gravando, âmbar = transcrevendo.
- **GPU opcional:** usa GPU NVIDIA quando disponível e passa para a CPU automaticamente.
- **Vários idiomas:** português por padrão; inglês, espanhol, detecção automática e outros idiomas do Whisper pela linha de comando.
- **Bancada de medição** para comparar modelos com a sua própria voz.

---

## Atalhos (padrão)

| Atalho | Ação |
|---|---|
| **Scroll Lock** | Iniciar ou concluir o ditado e inserir o texto |
| **Ctrl+Alt+A** | Ler em voz alta o texto selecionado; pressionar de novo interrompe |
| **Ctrl+Shift+Q** | Encerrar o SOLetrando |

Os três podem ser trocados em **Configurações** ou no menu do ícone da bandeja. A tecla de leitura também pode ser desativada. Atalhos globais valem em todos os programas; se uma combinação atrapalhar outro aplicativo, escolha outra.

---

## Requisitos

- *Windows* 10 ou 11
- Microfone
- Python 3.10 ou superior (somente para rodar a partir do código-fonte)
- GPU NVIDIA (opcional). As versões atuais do faster-whisper usam CUDA 12 e cuDNN 9; sem essas bibliotecas, o SOLetrando usa a CPU. Veja a seção sobre GPU no [README do faster-whisper](https://github.com/SYSTRAN/faster-whisper#gpu).
- Vozes do *Windows* no idioma da leitura (normalmente já existe voz em português no *Windows* em português)

---

## Instalação

### Opção A: executável pronto

1. Em [Releases](https://github.com/vitoralves82/SOLetrando/releases), baixe o `.zip` da versão mais recente.
2. Extraia o conteúdo.
3. Execute `install.bat` para criar atalhos na Área de Trabalho e na inicialização, ou abra `soletrando.exe` diretamente.

Não precisa de Python, Git nem terminal.

### Opção B: a partir do código-fonte

```powershell
git clone https://github.com/vitoralves82/SOLetrando.git
cd SOLetrando
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
.\.venv\Scripts\pythonw.exe soletrando.py
```

O `pythonw.exe` roda sem janela de console. Para ver as mensagens no terminal, use `python soletrando.py`. Para criar atalhos na Área de Trabalho e na inicialização: `python install.py`.

O SOLetrando **não usa PyTorch**; não é preciso instalá-lo.

### Opção C: gerar o executável

Depois da opção B, execute `build.bat`. O executável fica em `dist\soletrando\soletrando.exe`. Com o [Inno Setup](https://jrsoftware.org/isinfo.php) no PATH, o mesmo script gera o instalador em `installer_output\`.

### Atualização

- **Código-fonte:** `git pull` e `pip install -r requirements.txt`.
- **Executável:** baixe a nova versão em Releases. O `update.py` só oferece versões **posteriores** à instalada e se recusa a rodar numa pasta clonada do Git.

---

## Uso

### Ditar

1. Coloque o cursor no campo que receberá o texto.
2. Pressione a tecla de gravar e fale normalmente. A prévia aparece na caixa flutuante.
3. Pressione a mesma tecla para concluir. O texto final é colado no campo.

Se o texto não chegar ao destino, ele continua na área de transferência (Ctrl+V) e em **Copiar último ditado**.

### Ler um texto em voz alta

1. Selecione o texto em qualquer programa.
2. Pressione **Ctrl+Alt+A** (ou a tecla escolhida). Pressione de novo para parar.

Também é possível selecionar um trecho na caixa flutuante e clicar em **Ler**. Em **Configurações > Leitura** você escolhe idioma, voz e velocidade e ouve um exemplo. Se faltar voz no idioma, o aviso indica onde instalá-la no *Windows* (Configurações > Hora e idioma > Fala).

As opções de velocidade mostram fatores aproximados, como **Rápida (≈1,3×)**. A velocidade real depende da voz instalada.

**Escolha da voz**

- A lista mostra as vozes SAPI 5 do idioma, as mesmas de Painel de Controle > Fala. As vozes do Brasil aparecem primeiro.
- **Automática** usa a primeira voz do idioma (pt-BR para português). É o padrão.
- A escolha fica salva por idioma. Se a voz escolhida for desinstalada, a leitura usa a automática e avisa.
- Instalou uma voz com a janela aberta? Clique em **Atualizar lista**.
- As vozes naturais do Narrador do *Windows* 11 não são SAPI 5. Adaptadores de terceiros, não oficiais, podem expô-las ao SAPI 5; nesse caso, elas aparecem na lista.
- Vozes marcadas como **(online)** precisam de internet e enviam o texto lido a um serviço externo. Para manter a leitura local, desative as vozes online no programa que as instalou.

Alguns programas não informam a seleção aos recursos de acessibilidade do *Windows*. Nesses casos, o SOLetrando copia a seleção por um instante e restaura a área de transferência, mas **só quando ela contém texto simples**, para não perder imagens ou formatação copiadas antes. Se a leitura falhar, copie algo como texto simples (por exemplo, no bloco de notas) e tente de novo.

### Configurações

Um clique no ícone da bandeja abre a janela com as abas:

| Aba | Conteúdo |
|---|---|
| **Ditado** | Modelo, idioma, teclas de gravar e encerrar, modo de inserção, prévia e bip |
| **Leitura** | Tecla de leitura, idioma, voz e velocidade, botões Ouvir exemplo e Atualizar lista |
| **Vocabulário** | Termos preferenciais e correções automáticas (`ouvido = correto`) |
| **Caixa flutuante** | Tamanho (com prévia ao vivo) e quando ocultar |
| **Privacidade** | Histórico, registro técnico, área de transferência, o que fica salvo e botões para apagar |
| **Ajuda** | Guia rápido, versão, registro técnico e desinstalação |

O menu de clique direito continua oferecendo acesso rápido a teclas, idiomas, inserção, bip, último ditado, histórico e **Parar leitura**.

---

## Privacidade: o que fica salvo

Tudo fica em `%LOCALAPPDATA%\Soletrando`:

| Arquivo | Conteúdo | Quando |
|---|---|---|
| `soletrando_config.json` | Preferências, vocabulário e correções | Sempre; necessário para o aplicativo |
| `ultimo_ditado.txt` | Texto do último ditado | Sempre; usado por Copiar último ditado |
| `historico_ditados.txt` (e `.txt.1`) | Ditados com data e hora | Só com **Guardar histórico** marcado; gira ao passar de 2 MB |
| `soletrando.log` (e `.log.1`) | Eventos técnicos, tempos e erros | Sempre; até cerca de 1 MB mais uma cópia anterior |
| `models\` | Modelos de reconhecimento | Após o primeiro download |

O registro técnico **não** contém vocabulário nem correções (somente a quantidade). O texto ditado só entra nele com a opção **Incluir o texto ditado no registro técnico**, pensada para diagnóstico. As abas Privacidade e Ajuda têm botões para abrir a pasta e apagar histórico ou registro técnico.

O que pode sair do computador:

- O SOLetrando não envia áudio nem texto pela internet. Com o modelo já baixado, o carregamento não consulta a rede.
- O texto passa pela área de transferência para ser colado. Com **Não guardar os ditados no histórico da área de transferência** (ligado por padrão), o *Windows* é instruído a não guardá-lo no histórico (Win+V) nem sincronizá-lo entre dispositivos. Outros programas que monitoram a área de transferência ainda podem lê-lo.
- O programa que recebe o texto segue as próprias regras.
- Arquivos compartilhados manualmente (por exemplo, o registro técnico para suporte) levam o que contêm. Revise antes de enviar.

Desinstalar pelo *Windows* uma instalação feita com o instalador remove a pasta de dados, inclusive os modelos.

---

## Modelos

| Modelo | Parâmetros | Observação |
|---|---|---|
| `tiny`, `base`, `small` | 39 M a 244 M | Leves; úteis em CPU fraca, com mais erros |
| `medium` | 769 M | Intermediário |
| **`large-v3-turbo`** | 809 M | **Padrão.** Decodificador reduzido: bem mais rápido que o `large-v3` |
| `large-v3` | 1550 M | Mais pesado; pode errar menos em alguns vocabulários |

Segundo a OpenAI, o `turbo` é bem mais rápido, com pequena perda média de precisão, maior em alguns idiomas. Isso **não garante** o mesmo resultado para a sua voz, seu microfone e seus termos técnicos. Para decidir com dados, use a bancada abaixo. Memória de vídeo e tempos variam com a GPU e o tipo de cálculo (`float16`, `int8_float16`), por isso não são fixados aqui.

Na linha de comando:

```
--model     tiny, base, small, medium, large-v3-turbo (padrão), large-v3
--language  pt (padrão), en, es, fr, de... ou "auto" para detecção automática
```

### Bancada: comparar modelos com a sua voz

A pasta `tools` traz uma bancada que compara modelos com as mesmas gravações:

| Métrica | O que mostra |
|---|---|
| **WER** (*word error rate*) | Palavras trocadas, faltando ou sobrando, divididas pelo total da referência, ignorando pontuação e maiúsculas. É a medida dos *benchmarks* públicos |
| **WER formatado** | O mesmo, mas contando pontuação e maiúsculas. No ditado elas importam: um modelo que acerta as palavras e entrega tudo em minúsculas, sem vírgulas, obriga a revisar o texto |
| **Acerto de termos** | Porcentagem de siglas e nomes escritos exatamente como na referência (`IBAMA`, não `Ibama`) |
| Tempos e memória | Tempo após parar, tempo de uma atualização da prévia, fator de tempo real, pico de memória de vídeo e tempo de carga |

```powershell
# 1. Gravar amostras lendo frases (troque as frases por outras do seu dia a dia)
python tools\benchmark_modelos.py gravar tools\frases_exemplo_pt.txt amostras

# 2. Comparar os modelos na GPU, com o vocabulário e as correções já configurados
python tools\benchmark_modelos.py medir amostras --modelos large-v3-turbo large-v3 --usar-config --termos tools\termos_exemplo_pt.txt
```

Escreva o `.txt` de referência de cada amostra como você gostaria de ver o texto no documento (pontuação, maiúsculas, siglas e números). Com `--usar-config`, o vocabulário e as correções configurados também entram na lista de termos. O WER formatado é rigoroso (`9h30` contra `9:30` conta como erro); use-o para comparar modelos entre si, não como nota absoluta.

O resumo sai no terminal e os detalhes em `resultado_benchmark.csv`. Gravações e resultados ficam fora do Git por padrão (`.gitignore`). Os parâmetros de transcrição espelham os do aplicativo.

#### Testar um ajuste fino (*fine-tune*) do Whisper

Modelos da família Whisper ajustados para português podem ser convertidos para o formato do aplicativo (CTranslate2) e comparados na mesma bancada. A conversão precisa de `transformers` e `torch`; faça isso num ambiente separado para não misturar com o do aplicativo:

```powershell
python -m venv .venv-conversao
.\.venv-conversao\Scripts\activate
pip install ctranslate2 transformers torch
ct2-transformers-converter --model <repositorio-no-hugging-face> --output_dir modelos\meu-ajuste-ct2 --copy_files tokenizer.json preprocessor_config.json --quantization float16
```

Depois, no ambiente do aplicativo: `python tools\benchmark_modelos.py medir amostras --modelos large-v3 modelos\meu-ajuste-ct2 --usar-config`.

Dois cuidados:
- Copie o `preprocessor_config.json`. Modelos derivados do `large-v3` usam 128 faixas de frequência (*mel bins*); sem esse arquivo, o faster-whisper assume 80 e o modelo falha com erro de formato de entrada.
- Confira a licença do ajuste fino antes de usar no trabalho e compare também o WER formatado. Ajustes feitos com corpora acadêmicos podem aprender a escrever sem pontuação, com números por extenso ou com hesitações ("é...", "né"), o que reduz o WER desses corpora mas piora o texto ditado.

---

## Inicialização automática

- **Executável:** marque a opção durante a instalação ou use `install.bat`.
- **Código-fonte:** `python install.py`, ou copie `soletrando_startup.vbs` para `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\` e ajuste os caminhos dentro dele.

---

## Estrutura do projeto

```
SOLetrando/
├── soletrando.py          # Núcleo: captura, modelo, atalhos, inserção e bandeja
├── soletrando_config.py   # Opções, valores padrão e validação da configuração
├── soletrando_speech.py   # Leitura por voz e captura da seleção
├── soletrando_text.py     # Vocabulário, correções e união da prévia
├── soletrando_audio.py    # Bip sonoro
├── soletrando_ui.py       # Caixa flutuante e janela de Configurações
├── update.py              # Atualizador por Releases
├── install.py / .bat      # Atalhos na Área de Trabalho e na inicialização
├── soletrando.spec        # Geração do executável (PyInstaller)
├── installer.iss          # Instalador (Inno Setup)
├── build.bat              # Executável e instalador
├── tools/                 # Bancada de modelos, frases e termos de exemplo
├── tests/                 # Testes automatizados (python -m unittest discover -s tests)
└── version.txt
```

---

## Solução de problemas

| Problema | O que fazer |
|---|---|
| O texto não aparece no programa | Confira se o cursor estava no campo antes de gravar. O texto também fica na área de transferência e em **Copiar último ditado**. Em terminais, use o modo **Digitar** |
| A GPU não é usada | O registro técnico mostra `Modelo carregado: ... / cpu`. Confira drivers e bibliotecas CUDA 12 e cuDNN 9 (veja Requisitos) |
| Microfone não detectado | `python -c "import sounddevice; print(sounddevice.query_devices())"` e o microfone padrão do *Windows* |
| "Já existe uma instância" | Encerre `soletrando.exe` ou `pythonw.exe` no Gerenciador de Tarefas |
| Ícone não aparece na bandeja | Clique na seta `^` da barra de tarefas e arraste o ícone para a área visível |
| "O atalho X já está reservado por outro programa" | Outro aplicativo registrou a mesma tecla antes. Escolha outra em Configurações |
| Atalho não funciona num programa específico | Programas executados **como administrador** ignoram atalhos de programas comuns (proteção UIPI do *Windows*). Rode o SOLetrando como administrador também |
| A leitura diz que não há voz | Instale a voz em Configurações do *Windows* > Hora e idioma > Fala |
| A leitura não pega a seleção | Veja "Ler um texto em voz alta" acima |

### Por que o atalho antigo parava de funcionar

Versões antigas usavam um *hook* global de teclado (`WH_KEYBOARD_LL`, biblioteca `keyboard`): toda tecla digitada em qualquer programa passava por código Python. O *Windows* dá a esse *hook* um limite de tempo (`LowLevelHooksTimeout`, 300 ms por padrão) e o remove silenciosamente quando o limite estoura. Uma transcrição pesada ou o antivírus bastavam para o atalho morrer sem aviso.

Hoje os atalhos usam `RegisterHotKey`, a API do *Windows* feita para atalhos globais, sem *hook* e sem limite de tempo. Um monitor interno confere os atalhos a cada 10 segundos e os registra de novo se algum deixar de valer. Efeito colateral: o `Scroll Lock` usado como atalho não acende mais o LED do teclado; o estado aparece na cor do ícone.

---

## Créditos

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): motor de transcrição
- [OpenAI Whisper](https://github.com/openai/whisper): modelos de reconhecimento de fala
- [pystray](https://github.com/moses-palmer/pystray): ícone na bandeja
- [sounddevice](https://python-sounddevice.readthedocs.io/): captura de áudio

## Licença

MIT

---
---

# <a id="english"></a>English

<p align="center">
  <img src="icon_idle.png" alt="SOLetrando" width="128">
</p>

Free voice dictation and read-aloud for Windows that run on your own computer, powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) on an NVIDIA GPU or the CPU.

Press **Scroll Lock**, speak, press again: the text appears wherever the cursor is (Word, browser, Notepad, any app). Select some text and press **Ctrl+Alt+A** to hear it read aloud.

---

## Features

- **Local processing:** audio and text are processed on your computer. The internet is used to download the speech model the first time.
- **Dictation with live preview:** a floating panel shows the text while you speak; the final result is inserted once into the target field.
- **Read aloud** the text selected in any program, using the Windows voice you choose, with adjustable speed and its own hotkey.
- **Personal vocabulary and corrections** for names, acronyms, and recurring terms.
- **Last dictation and local history** to recover text later.
- **Configurable privacy:** the technical log never stores vocabulary or corrections, and dictations can be kept out of the Windows clipboard history (Win+V).
- **All preferences in one window** (click the tray icon), plus the right-click menu.
- **Tray icon** with state colors: yellow = ready, blue = recording, amber = transcribing.
- **Optional GPU:** uses an NVIDIA GPU when available and falls back to the CPU automatically.
- **Multiple languages:** Portuguese by default; English, Spanish, auto-detect, and other Whisper languages from the command line.
- **Benchmark tool** to compare models with your own voice.

---

## Hotkeys (default)

| Hotkey | Action |
|---|---|
| **Scroll Lock** | Start or finish dictation and insert the text |
| **Ctrl+Alt+A** | Read the selected text aloud; press again to stop |
| **Ctrl+Shift+Q** | Quit SOLetrando |

All three can be changed in **Configurações** (Settings) or in the tray menu. The read-aloud hotkey can also be disabled. Global hotkeys apply to every program; if a combination conflicts with another app, pick a different one.

---

## Requirements

- Windows 10 or 11
- Microphone
- Python 3.10 or later (only to run from source)
- NVIDIA GPU (optional). Current faster-whisper versions use CUDA 12 and cuDNN 9; without those libraries SOLetrando runs on the CPU. See the GPU section of the [faster-whisper README](https://github.com/SYSTRAN/faster-whisper#gpu).
- Windows voices for the read-aloud language (Portuguese Windows usually ships a Portuguese voice)

---

## Installation

### Option A: prebuilt executable

1. Download the latest `.zip` from [Releases](https://github.com/vitoralves82/SOLetrando/releases).
2. Extract it.
3. Run `install.bat` to create Desktop and Startup shortcuts, or open `soletrando.exe` directly.

No Python, Git, or terminal needed.

### Option B: from source

```powershell
git clone https://github.com/vitoralves82/SOLetrando.git
cd SOLetrando
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
.\.venv\Scripts\pythonw.exe soletrando.py
```

`pythonw.exe` runs without a console window. To see messages in the terminal, use `python soletrando.py`. To create Desktop and Startup shortcuts: `python install.py`.

SOLetrando **does not use PyTorch**; there is no need to install it.

### Option C: build the executable

After option B, run `build.bat`. The executable is written to `dist\soletrando\soletrando.exe`. With [Inno Setup](https://jrsoftware.org/isinfo.php) on the PATH, the same script also builds the installer in `installer_output\`.

### Updating

- **Source:** `git pull` and `pip install -r requirements.txt`.
- **Executable:** download the new version from Releases. `update.py` only offers versions **newer** than the installed one and refuses to run inside a Git clone.

---

## Usage

### Dictate

1. Place the cursor in the field that will receive the text.
2. Press the record hotkey and speak normally. The preview appears in the floating panel.
3. Press the same hotkey to finish. The final text is pasted into the field.

If the text does not reach the target, it stays on the clipboard (Ctrl+V) and under **Copiar último ditado** (Copy last dictation).

### Read text aloud

1. Select the text in any program.
2. Press **Ctrl+Alt+A** (or your chosen hotkey). Press again to stop.

You can also select part of the floating panel's text and click **Ler** (Read). Under **Configurações > Leitura** you choose the language, voice, and speed and can play a sample. If no voice is installed for that language, the warning explains where to add one in Windows (Settings > Time & language > Speech).

Speed options show approximate factors, such as **Rápida (≈1,3×)**. Actual speed depends on the installed voice.

**Choosing the voice**

- The list shows the SAPI 5 voices for the language, the same ones found in Control Panel > Speech. Brazilian voices come first.
- **Automática** (Automatic) uses the first voice for the language (pt-BR for Portuguese). This is the default.
- The choice is saved per language. If the chosen voice is uninstalled, reading falls back to the automatic voice and shows a warning.
- Installed a voice while the window was open? Click **Atualizar lista** (Refresh list).
- Windows 11 Narrator natural voices are not SAPI 5 voices. Unofficial third-party adapters can expose them to SAPI 5; in that case they show up in the list.
- Voices marked **(online)** need internet access and send the text being read to an external service. To keep reading local, turn off online voices in the program that installed them.

Some programs do not expose their selection to Windows accessibility. In that case SOLetrando briefly copies the selection and restores the clipboard, **but only when the clipboard holds plain text**, so images or rich formatting copied earlier are never lost. If reading fails, copy some plain text (for example, in Notepad) and try again.

### Settings window

A single click on the tray icon opens a window with these tabs:

| Tab | Contents |
|---|---|
| **Ditado** (Dictation) | Model, language, record and quit hotkeys, insertion mode, preview, and beep |
| **Leitura** (Reading) | Read-aloud hotkey, language, voice, and speed, sample and refresh-list buttons |
| **Vocabulário** (Vocabulary) | Preferred terms and automatic corrections (`heard = correct`) |
| **Caixa flutuante** (Floating panel) | Size (with live preview) and when to hide |
| **Privacidade** (Privacy) | History, technical log, clipboard option, what is stored, and delete buttons |
| **Ajuda** (Help) | Quick guide, version, technical log, and uninstall |

The right-click menu still offers quick access to hotkeys, languages, insertion mode, beep, last dictation, history, and **Parar leitura** (Stop reading).

---

## Privacy: what is stored

Everything lives in `%LOCALAPPDATA%\Soletrando`:

| File | Contents | When |
|---|---|---|
| `soletrando_config.json` | Preferences, vocabulary, and corrections | Always; required by the app |
| `ultimo_ditado.txt` | Text of the last dictation | Always; used by Copy last dictation |
| `historico_ditados.txt` (and `.txt.1`) | Dictations with date and time | Only with **Guardar histórico** (keep history) enabled; rotates after 2 MB |
| `soletrando.log` (and `.log.1`) | Technical events, timings, and errors | Always; up to about 1 MB plus one previous copy |
| `models\` | Speech recognition models | After the first download |

The technical log does **not** contain vocabulary or corrections (only their count). Dictated text is added to it only when the diagnostic option to include it is enabled. The Privacy and Help tabs have buttons to open the folder and delete the history or the technical log.

What can leave the computer:

- SOLetrando does not send audio or text over the internet. Once the model is downloaded, loading it does not contact the network.
- Text goes through the clipboard to be pasted. With the clipboard-history option (on by default), Windows is asked not to keep it in the clipboard history (Win+V) or sync it across devices. Other programs that monitor the clipboard can still read it.
- The program receiving the text follows its own rules.
- Files you share manually (for example, the technical log for support) carry whatever they contain. Review them before sending.

Uninstalling through Windows (when installed with the installer) removes the data folder, including the models.

---

## Models

| Model | Parameters | Notes |
|---|---|---|
| `tiny`, `base`, `small` | 39 M to 244 M | Light; useful on slow CPUs, with more errors |
| `medium` | 769 M | Middle ground |
| **`large-v3-turbo`** | 809 M | **Default.** Reduced decoder: much faster than `large-v3` |
| `large-v3` | 1550 M | Heavier; may make fewer errors on some vocabularies |

According to OpenAI, `turbo` is much faster with a small average accuracy loss, larger in some languages. That **does not guarantee** the same result for your voice, microphone, and technical terms. To decide with data, use the benchmark below. Video memory and timings depend on the GPU and compute type (`float16`, `int8_float16`), so they are not fixed here.

Command line:

```
--model     tiny, base, small, medium, large-v3-turbo (default), large-v3
--language  pt (default), en, es, fr, de... or "auto" for auto-detect
```

### Benchmark: compare models with your voice

The `tools` folder includes a benchmark that compares models on the same recordings:

| Metric | What it shows |
|---|---|
| **WER** (word error rate) | Substituted, missing, or extra words divided by the reference length, ignoring punctuation and case. This is what public benchmarks report |
| **Formatted WER** | The same, but punctuation and case count. They matter for dictation: a model that gets the words right but outputs lowercase text without commas forces you to edit it |
| **Term accuracy** | Share of acronyms and names written exactly as in the reference (`IBAMA`, not `Ibama`) |
| Timing and memory | Time after stopping, time for one preview update, real-time factor, peak video memory, and load time |

```powershell
# 1. Record samples by reading phrases (replace them with your own everyday phrases)
python tools\benchmark_modelos.py gravar tools\frases_exemplo_pt.txt amostras

# 2. Compare models on the GPU, using your configured vocabulary and corrections
python tools\benchmark_modelos.py medir amostras --modelos large-v3-turbo large-v3 --usar-config --termos tools\termos_exemplo_pt.txt
```

Write each sample's reference `.txt` the way you want the text to appear in your document (punctuation, case, acronyms, and numbers). With `--usar-config`, your configured vocabulary and corrections are added to the term list. Formatted WER is strict (`9h30` versus `9:30` counts as an error); use it to compare models with each other, not as an absolute score.

The summary is printed in the terminal and details go to `resultado_benchmark.csv`. Recordings and results are git-ignored by default. Transcription parameters mirror the app's.

#### Testing a Whisper fine-tune

Whisper-family models fine-tuned for Portuguese can be converted to the app's format (CTranslate2) and compared on the same benchmark. Conversion needs `transformers` and `torch`; do it in a separate environment so it does not mix with the app's:

```powershell
python -m venv .venv-conversao
.\.venv-conversao\Scripts\activate
pip install ctranslate2 transformers torch
ct2-transformers-converter --model <hugging-face-repository> --output_dir modelos\my-finetune-ct2 --copy_files tokenizer.json preprocessor_config.json --quantization float16
```

Then, in the app's environment: `python tools\benchmark_modelos.py medir amostras --modelos large-v3 modelos\my-finetune-ct2 --usar-config`.

Two cautions:
- Copy `preprocessor_config.json`. Models derived from `large-v3` use 128 mel bins; without that file, faster-whisper assumes 80 and the model fails with an input shape error.
- Check the fine-tune's license before using it at work, and compare formatted WER too. Fine-tunes trained on academic corpora may learn to write without punctuation, spell out numbers, or keep hesitations ("é...", "né"), which lowers WER on those corpora but makes dictated text worse.

---

## Auto-start with Windows

- **Executable:** tick the option during installation or run `install.bat`.
- **Source:** `python install.py`, or copy `soletrando_startup.vbs` to `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\` and adjust the paths inside it.

---

## Project structure

```
SOLetrando/
├── soletrando.py          # Core: capture, model, hotkeys, insertion, and tray
├── soletrando_config.py   # Options, defaults, and configuration validation
├── soletrando_speech.py   # Read-aloud and selection capture
├── soletrando_text.py     # Vocabulary, corrections, and preview merging
├── soletrando_audio.py    # Beep sound
├── soletrando_ui.py       # Floating panel and Settings window
├── update.py              # Updater based on Releases
├── install.py / .bat      # Desktop and Startup shortcuts
├── soletrando.spec        # Executable build (PyInstaller)
├── installer.iss          # Installer (Inno Setup)
├── build.bat              # Executable and installer
├── tools/                 # Model benchmark, sample phrases, and terms
├── tests/                 # Automated tests (python -m unittest discover -s tests)
└── version.txt
```

---

## Troubleshooting

| Problem | What to do |
|---|---|
| Text does not appear in the program | Make sure the cursor was in the field before recording. The text also stays on the clipboard and under Copy last dictation. In terminals, use **Digitar** (type) mode |
| GPU is not used | The technical log shows `Modelo carregado: ... / cpu`. Check drivers and the CUDA 12 and cuDNN 9 libraries (see Requirements) |
| Microphone not detected | `python -c "import sounddevice; print(sounddevice.query_devices())"` and the Windows default microphone |
| "Already running" | End `soletrando.exe` or `pythonw.exe` in Task Manager |
| Tray icon not visible | Click the `^` arrow on the taskbar and drag the icon to the visible area |
| "Hotkey X is already reserved by another program" | Another app registered the same key first. Pick a different one in Settings |
| Hotkey does not work inside a specific program | Programs running **as administrator** ignore hotkeys from normal programs (Windows UIPI protection). Run SOLetrando as administrator too |
| Read-aloud says there is no voice | Install the voice in Windows Settings > Time & language > Speech |
| Read-aloud does not get the selection | See "Read text aloud" above |

### Why the old hotkey used to stop working

Older versions used a global keyboard hook (`WH_KEYBOARD_LL`, `keyboard` library): every keystroke in any program ran Python code. Windows gives that hook a time budget (`LowLevelHooksTimeout`, 300 ms by default) and silently removes it when the budget is exceeded. A heavy transcription or an antivirus scan was enough to kill the hotkey without warning.

Hotkeys now use `RegisterHotKey`, the Windows API designed for global shortcuts, with no hook and no time budget. An internal monitor re-checks the hotkeys every 10 seconds and re-registers any that stopped working. Side effect: `Scroll Lock` used as a hotkey no longer toggles the keyboard LED; the state is shown by the tray icon color.

---

## Credits

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): transcription engine
- [OpenAI Whisper](https://github.com/openai/whisper): speech recognition models
- [pystray](https://github.com/moses-palmer/pystray): system tray icon
- [sounddevice](https://python-sounddevice.readthedocs.io/): audio capture

## License

MIT
