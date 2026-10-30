import time
from concurrent.futures import ThreadPoolExecutor

from app.anmeldeschutz import Anmeldeschutz


class Uhr:
    def __init__(self) -> None:
        self.jetzt = [0.0]

    def __call__(self) -> float:
        return self.jetzt[0]

    def weiter(self, sekunden: float) -> None:
        self.jetzt[0] += sekunden


def _schutz(**kwargs):
    uhr = Uhr()
    return uhr, Anmeldeschutz(uhr=uhr, **kwargs)


def _fehl(schutz, name, adresse):
    """Ein Versuch, der nicht gelingt: die Vormerkung bleibt stehen."""
    return schutz.versuch_beginnen(name, adresse)


def test_fuenf_fehlversuche_sperren_namen():
    _, schutz = _schutz()
    for _ in range(5):
        assert _fehl(schutz, "lp.anna", "1.1.1.1")
    assert not schutz.versuch_beginnen("lp.anna", "1.1.1.1")
    assert not schutz.versuch_beginnen("lp.anna", "2.2.2.2")


def test_abgelehnter_versuch_zeichnet_nichts_auf():
    uhr, schutz = _schutz()
    for _ in range(5):
        _fehl(schutz, "lp.anna", "1.1.1.1")
    uhr.weiter(500)
    for _ in range(10):
        assert not schutz.versuch_beginnen("lp.anna", "1.1.1.1")
    uhr.weiter(401)  # 901 nach den ersten Versuchen
    assert schutz.versuch_beginnen("lp.anna", "1.1.1.1")


def test_sperre_endet_nach_fenster():
    uhr, schutz = _schutz()
    for _ in range(5):
        _fehl(schutz, "lp.anna", "1.1.1.1")
    assert not schutz.versuch_beginnen("lp.anna", "1.1.1.1")
    uhr.weiter(901)
    assert schutz.versuch_beginnen("lp.anna", "1.1.1.1")


def test_gleitendes_fenster():
    uhr, schutz = _schutz()
    _fehl(schutz, "lp.anna", "a")
    uhr.weiter(600)
    for _ in range(4):
        _fehl(schutz, "lp.anna", "a")
    assert not schutz.versuch_beginnen("lp.anna", "a")
    uhr.weiter(301)  # der erste Versuch (t=0) ist raus, 4 verbleiben
    assert _fehl(schutz, "lp.anna", "a")
    assert not schutz.versuch_beginnen("lp.anna", "a")


def test_zwanzig_versuche_pro_adresse():
    _, schutz = _schutz()
    for i in range(20):
        assert _fehl(schutz, f"name{i}", "1.1.1.1")
    assert not schutz.versuch_beginnen("neu", "1.1.1.1")
    assert schutz.versuch_beginnen("neu", "2.2.2.2")


def test_erfolg_loescht_namen_und_eigenen_adressversuch():
    _, schutz = _schutz(max_pro_adresse=5)
    for _ in range(3):
        _fehl(schutz, "lp.anna", "1.1.1.1")
    assert schutz.versuch_beginnen("lp.anna", "1.1.1.1")  # der gelingende Versuch
    schutz.erfolg("lp.anna", "1.1.1.1")
    # Name frei, von der Adresse bleiben nur die 3 Fehlversuche
    assert schutz.versuch_beginnen("lp.anna", "2.2.2.2")
    assert schutz.versuch_beginnen("x", "1.1.1.1")
    assert schutz.versuch_beginnen("y", "1.1.1.1")
    assert not schutz.versuch_beginnen("z", "1.1.1.1")


def test_name_unabhaengig_von_schreibweise():
    _, schutz = _schutz()
    for _ in range(3):
        _fehl(schutz, "LP.Anna ", "a")
    for _ in range(2):
        _fehl(schutz, "lp.anna", "b")
    assert not schutz.versuch_beginnen("  Lp.ANNA", "c")


def test_speicher_begrenzt():
    uhr, schutz = _schutz(max_schluessel=10)
    for i in range(50):
        uhr.weiter(1)
        _fehl(schutz, "lp.anna", f"adresse{i}")
    assert len(schutz._eintraege) <= 10


def test_veraltete_eintraege_fallen_ohne_erneuten_zugriff_weg():
    uhr, schutz = _schutz()
    for i in range(30):
        _fehl(schutz, f"name{i}", f"adresse{i}")
    uhr.weiter(901)
    schutz.versuch_beginnen("jemand", "irgendwo")
    assert set(schutz._eintraege) == {"n:jemand", "a:irgendwo"}


def test_parallele_versuche_lassen_hoechstens_fuenf_durch():
    """Zwischen Vormerken und Ergebnis liegt Zeit (bcrypt): trotzdem hoechstens 5 pro Name."""
    _, schutz = _schutz(max_pro_adresse=1000)

    def versuch(i):
        if not schutz.versuch_beginnen("lp.anna", f"adresse{i}"):
            return False
        time.sleep(0.05)  # die Passwortpruefung
        return True

    with ThreadPoolExecutor(max_workers=30) as pool:
        ergebnisse = list(pool.map(versuch, range(30)))
    assert sum(ergebnisse) == 5
