# Root Makefile: builds the example and checks reproducibility.
VASM ?= .tools/vasm/vasmm68k_mot
OUT  ?= build

all: $(OUT)/HELLO.TOS $(OUT)/hello.st

$(OUT)/HELLO.TOS: examples/hello/hello.s
	@mkdir -p $(OUT)
	$(VASM) -Ftos -tos-flags=1 -no-opt -nosym -quiet -o $@ $<

$(OUT)/hello.st: $(OUT)/HELLO.TOS
	python3 tools/mkst.py $@ HELLO $<:AUTO/HELLO.PRG $<:HELLO.TOS

# Reproducibility: two successive assemblies give exactly the same bytes.
check: all
	$(VASM) -Ftos -tos-flags=1 -no-opt -nosym -quiet -o $(OUT)/HELLO2.TOS examples/hello/hello.s
	cmp $(OUT)/HELLO.TOS $(OUT)/HELLO2.TOS && echo "OK: reproducible build"
	python3 tools/prg_info.py $(OUT)/HELLO.TOS

clean:
	rm -rf $(OUT)
.PHONY: all check clean
