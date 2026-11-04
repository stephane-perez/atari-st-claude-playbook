; sndhplay.s - minimal SNDH test player (TOS program), 50 Hz VBL.
; Build (tools/sndh_record.py does it): vasmm68k_mot -Ftos -tos-flags=1 -no-opt -nosym
;   -DSUBTUNE=n -o PLAY.TOS sndhplay.s   with "tune.sndh" in the current folder.
; Plays sub-tune SUBTUNE forever: init, then play from the VBL ($70, chained to TOS).
	section	text
start:
	clr.l	-(sp)
	move.w	#$20,-(sp)		; Super
	trap	#1
	addq.l	#6,sp
	move.w	#$2700,sr
	moveq	#SUBTUNE,d0
	bsr	tune+0			; SNDH init
	move.l	$70.w,oldvbl
	move.l	#vbl,$70.w
	move.w	#$2300,sr
.wait:	bra.s	.wait

vbl:	movem.l	d0-a6,-(sp)
	bsr	tune+8			; SNDH play
	addq.l	#1,frames
	movem.l	(sp)+,d0-a6
	move.l	oldvbl(pc),-(sp)
	rts

oldvbl:	dc.l	0
frames:	dc.l	0
	even
tune:	incbin	"tune.sndh"
	even
