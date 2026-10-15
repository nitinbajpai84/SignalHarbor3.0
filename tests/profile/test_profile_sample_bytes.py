"""sample_bytes opens only a stored file by its own id: an id that is not the short hex the store makes is refused, never turned into a path."""
import pytest

from sh_platform.profile import reader, sample_bytes


def test_a_stored_file_is_read_by_its_id(plane):
    att = reader.attach(plane, 8, "Pia Profile", "s.csv", b"a,b\n1,2\n3,4\n")
    assert sample_bytes(plane, {"id": att["id"], "name": "s.csv"}) == b"a,b\n1,2\n3,4\n"


def test_an_id_that_climbs_out_of_the_files_folder_is_refused(plane):
    beside = plane.path("context", "profile", "secret.csv")  # one folder above the stored files
    plane.path("context", "profile", "files").mkdir(parents=True, exist_ok=True)
    beside.write_bytes(b"x,y\n1,2\n")
    with pytest.raises(OSError):
        sample_bytes(plane, {"id": "../secret", "name": "s.csv"})


@pytest.mark.parametrize("bad", ["", "..", "a/b", "A1B2", "zzzz", "abc def", "0" * 65])
def test_an_id_that_is_not_hex_is_refused(plane, bad):
    with pytest.raises(OSError):
        sample_bytes(plane, {"id": bad, "name": "s.csv"})
