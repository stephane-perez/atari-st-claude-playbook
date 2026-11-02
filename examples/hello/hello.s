; HELLO.TOS - minimal GEMDOS program, used to test the whole chain
; (vasm -> Hatari -> TOS 1.04 / 1.62 / 2.06 / 4.04).
; Assembly: vasmm68k_mot -Ftos -tos-flags=1 -o HELLO.TOS hello.s
;
; Repository convention: every delivered executable carries a version number
; (0.0.1, 0.0.2...) visible on screen, to keep track between builds.

        pea     msg(pc)
        move.w  #9,-(sp)        ; Cconws: display a string
        trap    #1
        addq.l  #6,sp

        move.w  #7,-(sp)        ; Crawcin: wait for a key
        trap    #1
        addq.l  #2,sp

        clr.w   -(sp)           ; Pterm0: back to the desktop
        trap    #1

msg:    dc.b    27,"E"          ; VT52: clear the screen
        dc.b    "HELLO ATARI ST - v0.0.1",13,10
        dc.b    "vasm + Hatari chain operational.",13,10
        dc.b    "Press a key...",0
        even
