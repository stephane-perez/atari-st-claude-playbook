// Minimal use: loop MUSIC.SGN from the hard disk (STE, supervisor mode), one update per frame.
// Build with the m68k-atari-mint cross compiler (docs/10, scripts/get-cross-mint.sh): -std=c++11 -Os, MiNTLib headers.
// Not compiled by `make`: adapt to your own tool chain.
#include <mint/osbind.h>
#include <mint/sysbind.h>
#include "dmastream.h"

static inline unsigned long vbl() { return *(volatile unsigned long*)0x466; }	// _frclock: VBLs since boot

int main()
{
	long ssp = Super(0);								// sound DMA and ACSI DMA are driven in supervisor mode

	if (!dmastream_open("MUSIC.SGN", /*unsigned_samples=*/false))		// false: samples already signed; true: standard 8-bit WAV
		if (!dmastream_open("MUSIC.WAV", true)) { Super(ssp); return 1; }
	// g_dmastream.raw: non blocking ACSI DMA reads usable; otherwise plain Fread (g_dmastream.rawstate = reason)
	long ring = dmastream_start();						// allocates the ring (free RAM - 20 KB), prefills it, starts the sound
	if (!ring) { Super(ssp); return 2; }

	unsigned long last = vbl();
	while (!Cconis())									// any key quits
	{
		unsigned long now = vbl();
		while (vbl() == now) {}								// wait for the next VBL
		unsigned long elapsed = vbl() - last; last = vbl();
		// ... the frame's work (drawing, logic) ...
		dmastream_update(elapsed > 1 ? (long)(elapsed - 1) : 0);	// once per frame, at the end; argument = VBLs lost by the previous frame
	}
	dmastream_stop();
	Super(ssp);
	return 0;
}
