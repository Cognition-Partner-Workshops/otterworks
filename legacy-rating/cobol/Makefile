# RATEPREM - GnuCOBOL build and run
#
#   make        build bin/RATEPREM
#   make run    rate ../fixtures/policies.dat into build/rated.dat
#   make clean

COBC      ?= cobc
COBCFLAGS ?= -x -std=default -fsign=EBCDIC -Wall -I copybooks
BIN       := bin/RATEPREM
BUILD     ?= build

.PHONY: all build run clean
all: build
build: $(BIN)

$(BIN): RATEPREM.cbl copybooks/POLREC.cpy copybooks/RATEOUT.cpy copybooks/RATETBL.cpy
	@mkdir -p bin
	$(COBC) $(COBCFLAGS) -o $@ RATEPREM.cbl

run: $(BIN)
	@mkdir -p $(BUILD)
	./run.sh ../fixtures/policies.dat $(BUILD)/rated.dat

clean:
	rm -rf bin $(BUILD)
