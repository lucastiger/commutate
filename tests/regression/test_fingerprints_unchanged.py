"""Layout fingerprints of ``generate_layouts(12, seed=0)`` recorded before T0256 (per-net rules, signal wires).

Extending the IR with optional gate/Kelvin wires, and DesignRules with per-net values, must leave both the
generator output and ``Layout.fingerprint()`` of layouts without signal wires unchanged.
"""
from moduleforge.generate.halfbridge import generate_layouts

FINGERPRINTS_SEED0 = (
    "2b249b4377eeb87b067810fcb6fa475f098eded05fad4675cba985971e730e41",
    "64aaa0bac850fc48ac838a6fc433faaa40fbe9c0d7dfba655c5ca9cb5847bcc2",
    "baf3a2bb0d3c592a1c49cc14a79566dbfe53c07241de8984b5017834eebeb175",
    "cafdd2e231ef474f9f4f9743e7acb91996ea1067bf9017e0baaf737058f7b56d",
    "642d2d2d86ababcce254eb3a3a24967469a75ff83b4b908cac396f59db33c900",
    "fac18f06f8fc923523bec2816cabf8b4ac35af7b67c91985a6b66b6182e6683b",
    "43a8014a2f3302f49268be44baaeebefd2a2bf9e1e7b6e4eddd17ef748fbc620",
    "dc16043850b00b9febfced5c86a0f515cfdf03927ebfcc5c690c85817d25a77f",
    "b53ded72c39d6741f113fbc91aeb22c2473b09a6749435a4a6a605e715961369",
    "b3d647ba6e9163a52d55378b455f6b55263423a1c77f24c42024751c2c71a73a",
    "98e0fcca3a62555ddfc17c7cf4e311ba4f58683fadfb488952539da701db593c",
    "0c5af7110829fa72c4a93ca9b6b16d50be493db24f13fc137ec5cef32ce4ca9f",
)


def test_generate_layouts_seed0_fingerprints_unchanged():
    got = tuple(lay.fingerprint() for lay in generate_layouts(12, seed=0))
    assert got == FINGERPRINTS_SEED0


def test_signal_wire_field_defaults_empty():
    lay = generate_layouts(1, seed=0)[0]
    assert lay.signal_wires == []
