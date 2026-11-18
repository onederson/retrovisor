from server.collectors import midia


def test_nome_app():
    assert midia._nome_app("Chrome") == "Chrome"
    assert midia._nome_app("Spotify.exe") == "Spotify"
    assert midia._nome_app("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify") == "Spotify"
    assert midia._nome_app(r"C:\Program Files\VideoLAN\VLC\vlc.exe") == "vlc"


def test_brave_fica_de_fora():
    ign = midia._ignorar({})
    assert midia._ignorado("Brave", ign)
    assert midia._ignorado("Brave.QCVPKLCBE6KRVSH5CQHUFUCMZQ", ign)
    assert not midia._ignorado("Chrome", ign)
    assert not midia._ignorado("Spotify.exe", midia._ignorar({"midia": {"ignorar": ["vlc"]}}))


def test_modo_velocidade():
    assert midia._modo_velocidade("Chrome", False) == "navegador"
    assert midia._modo_velocidade("MSEdge", False) == "navegador"
    assert midia._modo_velocidade("vlc.exe", False) == "vlc"
    assert midia._modo_velocidade("Spotify.exe", True) == "nativo"
    assert midia._modo_velocidade("Spotify.exe", False) is None


def test_teclas_velocidade():
    assert midia._teclas_velocidade("navegador", 1.0) == "<" * 7 + ">" * 3
    assert midia._teclas_velocidade("navegador", 0.25) == "<" * 7
    assert midia._teclas_velocidade("navegador", 2.0) == "<" * 7 + ">" * 7
    assert midia._teclas_velocidade("vlc", 1.0) == "="
    assert midia._teclas_velocidade("vlc", 1.5) == "=" + "]" * 5
    assert midia._teclas_velocidade("vlc", 0.5) == "=" + "[" * 5


def test_escolher_janela_midia():
    from server.janelas import escolher_janela_midia as esc
    js = [
        (1, "code.exe", "", "midia.py - VS Code"),
        (2, "chrome.exe", "", "Gmail - Google Chrome"),
        (3, "chrome.exe", "", "Meu Video - YouTube - Google Chrome"),
        (4, "microsoft.media.player.exe", "Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic", "Media Player"),
        (5, "vlc.exe", "", "filme.mkv - VLC media player"),
        (6, "firefox.exe", "", "Outro Video — Mozilla Firefox"),
    ]
    assert esc(js, "Chrome", "Meu Video") == 3
    assert esc(js, "Chrome", "nao esta no titulo") == 2
    assert esc(js, "Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic", "musica") == 4
    assert esc(js, "vlc.exe", "filme") == 5
    assert esc(js, "308046B0AF4A39CB", "Outro Video") == 6
    assert esc(js, "Spotify.exe", "nada") is None


def test_id_unico_repete_app():
    vistos = {}
    assert [midia._id_unico("Chrome", vistos) for _ in range(3)] == ["Chrome", "Chrome#2", "Chrome#3"]
