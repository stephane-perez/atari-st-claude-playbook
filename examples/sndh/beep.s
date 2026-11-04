; beep.s - a minimal original SNDH tune, used to test tools/ym_emu.py,
; tools/sndh_record.py and tools/m68k_recdis.py (no third-party data).
; Build: vasmm68k_mot -Fbin -no-opt -quiet -o BEEP.SNDH beep.s
; Two sub-tunes (a rising and a falling scale on channel A), 8 notes of
; 10 frames each, then silence: after the last note, play returns without
; touching the YM (as many real players do). The YM writes end with the
; move.w sr,-(a7) ... rte idiom (restores SR and returns), which Unicorn does
; not execute as a 68000 does: ym_emu.py handles it.
	bra.w	init			; SNDH: +0 init (d0 = sub-tune 1..n)
	bra.w	exit			;       +4 exit
	bra.w	play			;       +8 play, 50 Hz
	dc.b	"SNDH"
	dc.b	"TITLBeep test",0
	dc.b	"COMMatari-st-claude-playbook",0
	dc.b	"YEAR2026",0
	dc.b	"##02"
	dc.b	"TC50"
	dc.b	"HDNS"
	even

init:	lea	notes_up(pc),a0
	cmp.w	#2,d0
	bne.s	.set
	lea	notes_down(pc),a0
.set:	lea	ptr(pc),a1
	move.l	a0,(a1)
	lea	count(pc),a1
	move.w	#10,(a1)
	rts

exit:	lea	$ffff8800.w,a0
	move.b	#8,(a0)			; channel A volume 0
	clr.b	2(a0)
	rts

play:	move.l	ptr(pc),a0
	move.w	(a0),d0
	bmi.s	.done			; finished: no YM write at all
	lea	count(pc),a1
	subq.w	#1,(a1)
	bne.s	.write
	move.w	#10,(a1)
	addq.l	#2,a0
	lea	ptr(pc),a1
	move.l	a0,(a1)
	move.w	(a0),d0
	bmi.s	silence
.write:	bsr.s	ym_note
.done:	rts

silence:
	lea	$ffff8800.w,a0
	move.b	#8,(a0)
	clr.b	2(a0)
	rts

; d0 = tone period of channel A; ends with move.w sr,-(a7) ... rte
ym_note:
	move.w	sr,-(a7)
	or.w	#$0700,sr
	lea	$ffff8800.w,a0
	move.b	#0,(a0)
	move.b	d0,2(a0)
	lsr.w	#8,d0
	move.b	#1,(a0)
	move.b	d0,2(a0)
	move.b	#7,(a0)
	move.b	(a0),d0			; keep the I/O port bits 6-7
	and.b	#$c0,d0
	or.b	#$3e,d0			; tone A only
	move.b	d0,2(a0)
	move.b	#8,(a0)
	move.b	#12,2(a0)
	rte

ptr:	dc.l	0
count:	dc.w	0
notes_up:	dc.w	956,851,758,716,638,568,506,478,-1
notes_down:	dc.w	478,506,568,638,716,758,851,956,-1
