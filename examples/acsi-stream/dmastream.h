//======================================================================================================================
//	dmastream.h - STE DMA sound: loops a WAV file streamed from disk (8-bit stereo, 25 kHz)
//----------------------------------------------------------------------------------------------------------------------
//	Neither AGT (its sound system mixes tracker music into a DMA ring buffer, it doesn't read files) nor the stsys10
//	framework (dma.s: preloaded samples, switched by VBL count) provides disk streaming, hence this module.
//
//	principle:
//	- the STE DMA chip loops over a ring buffer (as big as the free RAM allows, up to DMASTREAM_RING_MAX) in 'repeat' mode, by itself, forever
//	- dmastream_update() is called once per frame (any rate >= ~1 per 0.3 s works): it reads where the DMA is, and
//	  refills the part of the ring that has already been played with the next bytes of the file (GEMDOS Fread, at most
//	  DMASTREAM_CHUNK bytes per call so that a frame is never blocked for long on a slow disk)
//	- at the end of the 'data' chunk the file is rewound (Fseek) and the stream continues with no gap
//	- WAV 8-bit samples are unsigned by definition (silence = $80) while the STE wants signed ones: the sign is flipped
//	  on the fly (unless the file is already signed: dmastream_open(name, false) skips the work, saving ~3.5% of the CPU)
//	the frequency is not changed: 25000 Hz in the file is played at the STE's 25033 Hz (+0.13%)
//
//	usage (supervisor mode, like the rest of the demo):
//		if (dmastream_open("MUSIC.WAV")) dmastream_start();	// prefills the ring, starts the DMA
//		... each frame:	dmastream_update();
//		... at exit:	dmastream_stop();
//----------------------------------------------------------------------------------------------------------------------
#ifndef dmastream_h_
#define dmastream_h_

#include <mint/sysbind.h>
#include "dmaraw.h"

#ifndef DMASTREAM_RAW
#define DMASTREAM_RAW		1				// 1 = try the non blocking ACSI DMA reads (dmaraw.h) first; plain Fread if the checks fail
#endif

#ifndef DMASTREAM_RING_MAX
#define DMASTREAM_RING_MAX	(512L*1024)		// biggest ring requested (10.5 s of 25 kHz stereo); the real size depends on the free RAM
#endif
#ifndef DMASTREAM_RING_MIN
#define DMASTREAM_RING_MIN	(16L*1024)		// smallest usable ring
#endif
#ifndef DMASTREAM_RESERVE
#define DMASTREAM_RESERVE	(20L*1024)		// RAM left free for the system (GEMDOS/driver buffers, stack) when sizing the ring
#endif
// DMASTREAM_CHUNK (multiple of 512): forces a fixed read size instead of the adaptive one (benchmarks)
#ifndef DMASTREAM_MAXREADS
#define DMASTREAM_MAXREADS	1				// max Fread calls per dmastream_update(): one disk access per frame at most
#endif
#ifndef DMASTREAM_MARGIN
#define DMASTREAM_MARGIN	2048			// bytes kept between the refill point and the DMA read pointer
#endif
#ifndef DMASTREAM_RATE
#define DMASTREAM_RATE		2				// 0 = 6258, 1 = 12517, 2 = 25033, 3 = 50066 Hz
#endif

#ifndef DMASTREAM_ADAPT
#define DMASTREAM_ADAPT		1				// 1 = the read size adapts itself to the disk (the one that loses the fewest VBLs wins)
#endif
#ifndef DMASTREAM_WINDOW
#define DMASTREAM_WINDOW	131072L			// bytes read per measurement window (about 2.6 s of music)
#endif
static const long g_dmastream_sizes[8] = { 2048, 4096, 8192, 12288, 16384, 24576, 32768, 49152 };

struct dmastream_t
{
	short	fh;						// GEMDOS file handle (<0: closed)
	long	dataoff;					// file offset of the first sample
	long	datalen;					// bytes of samples in the file
	long	remaining;					// bytes of samples not yet read in this pass
	long	fpos;						// current file offset
	long	wr;						// ring offset where the next bytes are written
	long	played;						// total bytes played by the DMA (updated at each dmastream_update)
	long	written;					// total bytes written to the ring
	long	lastpos;					// DMA ring offset at the previous update
	long	reads;						// number of Fread calls (statistics)
	long	underruns;					// number of times the DMA overtook the disk (statistics)
	long	loops;						// number of times the file has been rewound
	long	lasterr;					// result of the last Fopen (negative GEMDOS error code)
	long	ringsize;					// ring size in bytes (multiple of 512)
	long	maxread;					// longest Fread so far, in 200 Hz ticks
	long	minbuf;						// lowest amount of buffered audio seen, in bytes
	unsigned char *ring;
	long	chunk;						// bytes per Fread right now (adaptive)
	short	cidx;						// index of 'chunk' in g_dmastream_sizes
	long	acc_lost, acc_bytes;		// adaptation: VBLs lost by the frames / bytes read, in the current window
	short	base, probe, quiet;			// adaptation state: size kept, probe in progress (0 none, 1 bigger, 2 smaller), windows since the last probe
	long	cost[8];					// measured cost (VBLs lost per 1000 KB read) for each size, <0 = unknown
	bool	raw;						// reading through the ACSI DMA (dmaraw.h) instead of Fread
	short	rawstate;					// result of the dmaraw probe (see dmaraw.h), 0 = not tried
	bool	pending;					// a DMA read is running
	bool	pbounce;					// ... into the bounce buffer (the sector crosses the end of the ring)
	long	pbytes;						// ... number of bytes
	short	pframes;					// frames the pending read has lasted
	short	flock;						// saved value of TOS 'flock' ($43e)
	long	rawfail;					// number of times the raw reads failed (then Fread takes over)
	bool	flip;						// flip the sign bit of the samples read (file holds unsigned samples)
	bool	running;
};

static dmastream_t g_dmastream;										// zero at start; dmastream_open() sets the rest
static unsigned char g_dmastream_bounce[512 + 16] __attribute__((aligned(4)));
static unsigned char g_dmastream_hdr[512] __attribute__((aligned(4)));

#define DMA_CTRL	(*(volatile unsigned char*)0xffff8901)
#define DMA_BASEH	(*(volatile unsigned char*)0xffff8903)
#define DMA_BASEM	(*(volatile unsigned char*)0xffff8905)
#define DMA_BASEL	(*(volatile unsigned char*)0xffff8907)
#define DMA_CNTH	(*(volatile unsigned char*)0xffff8909)
#define DMA_CNTM	(*(volatile unsigned char*)0xffff890b)
#define DMA_CNTL	(*(volatile unsigned char*)0xffff890d)
#define DMA_ENDH	(*(volatile unsigned char*)0xffff890f)
#define DMA_ENDM	(*(volatile unsigned char*)0xffff8911)
#define DMA_ENDL	(*(volatile unsigned char*)0xffff8913)
#define DMA_MODE	(*(volatile unsigned char*)0xffff8921)
#define MW_DATA		(*(volatile unsigned short*)0xffff8922)
#define MW_MASK		(*(volatile unsigned short*)0xffff8924)

// LMC1992 volume/tone chip, through the STE microwire interface
static inline void dmastream_microwire(unsigned short cmd)
{
	MW_MASK = 0x07ff;
	MW_DATA = cmd;
	for (long n = 0; n < 200000 && MW_MASK != 0x07ff; ++n) {}	// the mask register rotates until the 16 bits have been sent
}

static inline unsigned long dmastream_dmaaddr()
{
	unsigned long a, b;
	do {
		a = ((unsigned long)DMA_CNTH << 16) | ((unsigned long)DMA_CNTM << 8) | DMA_CNTL;
		b = ((unsigned long)DMA_CNTH << 16) | ((unsigned long)DMA_CNTM << 8) | DMA_CNTL;
	} while (a != b);					// the counter ripples while the DMA is running: read it until it is stable
	return a;
}

static inline long dmastream_dmapos()
{
	long p = (long)dmastream_dmaaddr() - (long)g_dmastream.ring;
	if (p < 0) p = 0;
	if (p >= g_dmastream.ringsize) p = g_dmastream.ringsize - 2;
	return p & ~1L;
}

// open the file and parse its header (RIFF/WAVE, PCM, 8 bits, stereo). returns false if the file can't be used
static bool dmastream_open(const char *name, bool unsigned_samples = true)
{
	dmastream_t& s = g_dmastream;
	s.flip = unsigned_samples; s.fh = -1; s.minbuf = 0x7fffffffL;
	for (int i = 0; i < 8; ++i) s.cost[i] = -1;
	long h = Fopen(name, S_READ);
	g_dmastream.lasterr = h;
	if (h < 0) return false;
	s.fh = (short)h;
	long n = Fread(s.fh, 512, g_dmastream_hdr);	// one whole sector: keeps the following reads sector aligned
	if (n < 44 || g_dmastream_hdr[0] != 'R' || g_dmastream_hdr[8] != 'W')
	{
		Fclose(s.fh); s.fh = -1; return false;
	}
	// walk the RIFF chunks inside this first sector (fmt, then data; the header is normally 44 bytes)
	long p = 12; bool fmt_ok = false; s.dataoff = 0;
	while (p + 8 <= n)
	{
		const unsigned char *c = g_dmastream_hdr + p;
		long sz = (long)c[4] | ((long)c[5] << 8) | ((long)c[6] << 16) | ((long)c[7] << 24);
		if (c[0] == 'f' && c[1] == 'm' && c[2] == 't')
		{
			unsigned fmt = c[8] | (c[9] << 8), ch = c[10] | (c[11] << 8), bits = c[22] | (c[23] << 8);
			fmt_ok = (fmt == 1 && ch == 2 && bits == 8);			// PCM, stereo, 8 bits
		}
		else if (c[0] == 'd' && c[1] == 'a' && c[2] == 't' && c[3] == 'a')
		{
			s.dataoff = p + 8; s.datalen = sz & ~1L; break;
		}
		p += 8 + sz + (sz & 1);
	}
	if (!fmt_ok || s.dataoff == 0 || s.datalen < DMASTREAM_RING_MIN)
	{
		Fclose(s.fh); s.fh = -1; return false;
	}
#if DMASTREAM_RAW
	{	// can the file be read by the ACSI DMA, without blocking? (needs a 32 KB scratch buffer)
		unsigned char *tmp = (unsigned char*)Malloc(32768);
		if (tmp && (long)tmp > 0)
		{
			s.raw = dmraw_probe(s.fh, s.dataoff + s.datalen, tmp);
			s.rawstate = g_dmraw.state;
			Mfree(tmp);
		}
		else s.rawstate = -7;
	}
#endif
	return true;
}

// flip the sign bit of every byte (WAV 8-bit = unsigned, STE DMA = signed). hand-written because it is the one hot loop
// of the streamer: 8 x 'eor.l d,(a)+' per 32 bytes = about 5.6 cycles per byte (a plain C loop costs ~8)
static inline void dmastream_flipsign(unsigned char *p, long n)
{
	unsigned long m = 0x80808080UL;
	long blocks = n >> 5;
	if (blocks > 0)
		__asm__ volatile(
			"1:\n\t"
			"eor.l %2,(%0)+\n\teor.l %2,(%0)+\n\teor.l %2,(%0)+\n\teor.l %2,(%0)+\n\t"
			"eor.l %2,(%0)+\n\teor.l %2,(%0)+\n\teor.l %2,(%0)+\n\teor.l %2,(%0)+\n\t"
			"subq.l #1,%1\n\tbne.b 1b"
			: "+a"(p), "+d"(blocks) : "d"(m) : "memory", "cc");
	for (long i = (n & 31) >> 2; i > 0; --i) { *(unsigned long*)p ^= m; p += 4; }
	if (n & 2) *(unsigned short*)p ^= 0x8080;
}

// bytes the next Fread asks for: sector alignment first, then whole chunks; never past the end of the data or of the ring
static inline long dmastream_nextpiece()
{
	dmastream_t& s = g_dmastream;
	long n = (s.fpos & 511) ? 512 - (s.fpos & 511) : s.chunk;
	if (n > s.remaining) n = s.remaining;
	if (n > s.ringsize - s.wr) n = s.ringsize - s.wr;
	return n;
}

// adaptation: a read that outlasts the idle time of the frame makes the next frames late. each size is judged by the VBLs
// the frames lost per MB streamed while it was used (measured on the real disk, not guessed). the current size is kept for a
// while, then the next bigger and the next smaller sizes are each tried for one window (about 2.6 s of music); the best of
// the three is kept (a change needs a 15% gain, so noise doesn't make it wander), and so on, to follow the load of the scenario
static void dmastream_adapt()
{
	dmastream_t& s = g_dmastream;
	long cost = (s.acc_lost * 1024L * 1000L) / s.acc_bytes;			// VBLs lost per MB streamed
	s.acc_lost = 0; s.acc_bytes = 0;
	long maxchunk = s.ringsize / 3;
	int lo = s.base - 1, hi = s.base + 1;
	bool hi_ok = hi < 8 && g_dmastream_sizes[hi] <= maxchunk, lo_ok = lo >= 0;
	if (s.probe == 0)											// measuring the base size
	{
		s.cost[s.base] = s.cost[s.base] < 0 ? cost : (s.cost[s.base] + cost) / 2;
		if (++s.quiet < 6) return;
		s.quiet = 0;
		if (s.cost[s.base] < 5) return;							// (almost) no VBL lost: nothing to gain
		if (lo_ok) s.cost[lo] = -1;
		if (hi < 8) s.cost[hi] = -1;
		if (hi_ok) { s.probe = 1; s.cidx = hi; }
		else if (lo_ok) { s.probe = 2; s.cidx = lo; }
	}
	else
	{
		s.cost[s.cidx] = cost;
		if (s.probe == 1 && lo_ok) { s.probe = 2; s.cidx = lo; }
		else													// all probes done: keep the best
		{
			int best = s.base;
			if (lo_ok && s.cost[lo] >= 0 && s.cost[lo] * 100 < s.cost[best] * 85) best = lo;
			if (hi_ok && s.cost[hi] >= 0 && s.cost[hi] * 100 < s.cost[best] * (best == s.base ? 100 : 85)) best = hi;	// equal: the bigger one
			s.probe = 0; s.base = best; s.cidx = best;
			for (int i = 0; i < 8; ++i) if (i != best) s.cost[i] = -1;
		}
	}
	s.chunk = g_dmastream_sizes[s.cidx];
}

// read the next piece of the file into the ring (the caller has checked that there is room). returns false on error
static bool dmastream_readpiece()
{
	dmastream_t& s = g_dmastream;
	long n = dmastream_nextpiece();
	long t0 = *(volatile long*)0x4ba;
	long got = Fread(s.fh, n, s.ring + s.wr);
	long dt = *(volatile long*)0x4ba - t0;
	if (dt > s.maxread) s.maxread = dt;
	++s.reads;
	if (got <= 0) return false;
	got &= ~1L;
	if (n == s.chunk && got == n && s.running) s.acc_bytes += got;
	if (s.flip) dmastream_flipsign(s.ring + s.wr, got);
	s.wr += got; if (s.wr >= s.ringsize) s.wr = 0;
	s.written += got; s.fpos += got; s.remaining -= got;
	if (s.remaining <= 0)								// end of the samples: rewind, the stream goes on with no gap
	{
		if (Fseek(s.dataoff, s.fh, 0) < 0) return false;
		s.fpos = s.dataoff; s.remaining = s.datalen; ++s.loops;
	}
	return true;
}

// ---- reading through the ACSI DMA

// 'got' bytes have been put in the ring at 'wr': advance (the end of the samples restarts the file, the tail < 512 bytes is dropped)
static void dmastream_commit(long got)
{
	dmastream_t& s = g_dmastream;
	s.wr += got; if (s.wr >= s.ringsize) s.wr -= s.ringsize;
	s.written += got; s.fpos += got; s.remaining -= got;
}

// starts the next piece: a few sectors read by DMA (s.pending = true, the result comes later), or the 468 bytes left in the first
// sector (copied from the header sector, nothing pending). returns false if there is nothing to do now (no room)
static bool dmastream_rawnext(long buffered, long maxsec, long minsec)
{
	dmastream_t& s = g_dmastream;
	long free_ = s.ringsize - DMASTREAM_MARGIN - buffered;
	if ((s.fpos & 511) == 0 && s.remaining < 512) { s.fpos = s.dataoff; s.remaining = s.datalen; ++s.loops; }	// end: start again
	if (s.fpos & 511)											// rest of the first sector
	{
		long n = 512 - (s.fpos & 511);
		if (n > s.remaining) n = s.remaining;
		long fit = (s.ringsize - s.wr) & ~1L; if (n > fit) n = fit;
		if (n <= 0 || free_ < n) return false;
		const unsigned char *src = g_dmastream_hdr + (s.fpos & 511);
		for (long i = 0; i < n; ++i) s.ring[s.wr + i] = src[i];
		if (s.flip) dmastream_flipsign(s.ring + s.wr, n & ~1L);
		dmastream_commit(n);
		return true;
	}
	long sec = free_ / 512, rs = s.remaining / 512;
	if (sec > maxsec) sec = maxsec;
	if (sec > rs) sec = rs;
	if (sec <= 0 || (sec < minsec && sec < rs)) return false;
	long fit = (s.ringsize - s.wr) / 512;
	unsigned char *dest; bool bounce = false;
	if (fit >= 1) { if (sec > fit) sec = fit; dest = s.ring + s.wr; }
	else { sec = 1; dest = g_dmastream_bounce; bounce = true; }			// the sector straddles the end of the ring: read it aside, copy it in two parts
	if (!dmraw_start(dest, g_dmraw.lba0 + (unsigned long)(s.fpos >> 9), (int)sec, g_dmraw.icd, g_dmraw.idbits, 3000))
	{
		s.rawfail = 1000 + sec; s.raw = false; return false;
	}
	s.pending = true; s.pbounce = bounce; s.pbytes = sec * 512; s.pframes = 0; ++s.reads;
	return true;
}

// the pending read has finished OK: its bytes join the ring
static void dmastream_rawdone()
{
	dmastream_t& s = g_dmastream;
	long got = s.pbytes;
	s.pending = false;
	if (s.pbounce)
	{
		long k = s.ringsize - s.wr;								// < 512, even
		if (s.flip) dmastream_flipsign(g_dmastream_bounce, got);
		for (long i = 0; i < k; ++i) s.ring[s.wr + i] = g_dmastream_bounce[i];
		for (long i = k; i < got; ++i) s.ring[i - k] = g_dmastream_bounce[i];
	}
	else if (s.flip) dmastream_flipsign(s.ring + s.wr, got);
	dmastream_commit(got);
}

// a raw read went wrong: from now on Fread does the work, from the same point of the file
static void dmastream_rawfail()
{
	dmastream_t& s = g_dmastream;
	ACSI_MODE = 0x80;
	s.raw = false; s.pending = false; ++s.rawfail;
	Fseek(s.fpos, s.fh, 0);
}

static void dmastream_update_raw(long buffered)
{
	dmastream_t& s = g_dmastream;
	if (s.pending)
	{
		int r = dmraw_poll();
		if (r == 0) { if (++s.pframes > 60) dmastream_rawfail(); return; }	// 60 frames = 1.2 s without an answer: give up
		if (r < 0) { dmastream_rawfail(); return; }
		dmastream_rawdone();
		buffered = s.written - s.played;
	}
	if (!dmastream_rawnext(buffered, 8, 4) && !s.raw) dmastream_rawfail();
}

// refill the ring: call once per frame
// 'defer' = the caller is running late (previous frame took more than one VBL): skip the disk work this time as long as
// the ring still holds more than half of its capacity, so that the frame can catch up
static void dmastream_update(long lost = 0)
{
	dmastream_t& s = g_dmastream;
	if (!s.running) return;
	bool defer = lost > 0;
#if DMASTREAM_ADAPT
	s.acc_lost += lost;
	if (s.acc_bytes >= DMASTREAM_WINDOW) dmastream_adapt();
#endif
	long pos = dmastream_dmapos();
	long d = pos - s.lastpos; if (d < 0) d += s.ringsize;
	s.played += d;									// valid as long as we are called at least once per ring period
	s.lastpos = pos;
	long buffered = s.written - s.played;
	if (buffered < 0)								// underrun: the DMA went past the data. resynchronise just ahead of the DMA
	{
		++s.underruns;
		s.wr = pos + DMASTREAM_MARGIN; if (s.wr >= s.ringsize) s.wr -= s.ringsize;
		s.written = s.played + DMASTREAM_MARGIN;
		buffered = DMASTREAM_MARGIN;
	}
	if (buffered < s.minbuf) s.minbuf = buffered;
	if (s.raw) { dmastream_update_raw(buffered); return; }
	if (defer && buffered > s.ringsize / 2) return;
	for (int k = 0; k < DMASTREAM_MAXREADS; ++k)
	{
		long free_ = s.ringsize - DMASTREAM_MARGIN - buffered;
		if (free_ < dmastream_nextpiece()) break;					// wait until the whole piece fits
		if (!dmastream_readpiece()) { s.running = false; DMA_CTRL = 0; return; }
		buffered = s.written - s.played;
	}
}

// fill the ring from the start of the samples and start the DMA (the ring is allocated)
static bool dmastream_begin()
{
	dmastream_t& s = g_dmastream;
	DMA_CTRL = 0;
	s.pending = false; s.acc_lost = 0; s.acc_bytes = 0;
	s.wr = 0; s.written = 0; s.played = 0; s.lastpos = 0;
	if (s.raw)													// prefill with big DMA reads, waiting for each one
	{
		s.fpos = s.dataoff; s.remaining = s.datalen;
		for (;;)
		{
			if (!dmastream_rawnext(s.written, 32, 1)) break;
			if (s.pending)
			{
				if (dmraw_wait(3000000) <= 0) { dmastream_rawfail(); break; }
				dmastream_rawdone();
			}
		}
		if (!s.raw) { s.wr = 0; s.written = 0; }					// failed: start again with Fread
	}
	if (!s.raw)
	{
		if (Fseek(512, s.fh, 0) < 0) return false;
		long first = (512 - s.dataoff) & ~1L;
		if (first > s.datalen) first = s.datalen;
		for (long i = 0; i < first; ++i) s.ring[i] = g_dmastream_hdr[s.dataoff + i];
		if (s.flip) dmastream_flipsign(s.ring, first);
		s.wr = first; s.written = first; s.fpos = 512; s.remaining = s.datalen - first;
		// prefill (the DMA is not running yet: 'played' stays 0)
		while (s.written + dmastream_nextpiece() <= s.ringsize - DMASTREAM_MARGIN)
			if (!dmastream_readpiece()) return false;
	}
	unsigned long a = (unsigned long)s.ring, e = a + (unsigned long)s.ringsize;
	DMA_BASEH = (unsigned char)(a >> 16); DMA_BASEM = (unsigned char)(a >> 8); DMA_BASEL = (unsigned char)a;
	DMA_ENDH = (unsigned char)(e >> 16);  DMA_ENDM = (unsigned char)(e >> 8);  DMA_ENDL = (unsigned char)e;
	DMA_MODE = (unsigned char)DMASTREAM_RATE;				// bit 7 = 0: stereo, bits 0-1: rate
	dmastream_microwire(0x4E8);							// master volume 40 (0 dB)
	dmastream_microwire(0x554);							// left volume 20 (0 dB)
	dmastream_microwire(0x514);							// right volume 20 (0 dB)
	dmastream_microwire(0x446);							// bass: 6 = flat (0 dB)
	dmastream_microwire(0x486);							// treble: 6 = flat (0 dB)
	dmastream_microwire(0x401);							// mixer: DMA + YM
	s.minbuf = 0x7fffffffL;
	s.running = true;
	DMA_CTRL = 3;									// play, repeat (loop on the ring)
	return true;
}

// allocate the ring (as big as the free RAM allows), fill it, set up the DMA and start it. returns the ring size (0 = failed)
static long dmastream_start(long maxring = DMASTREAM_RING_MAX)
{
	dmastream_t& s = g_dmastream;
	long avail = (long)Malloc(-1) - DMASTREAM_RESERVE;				// biggest free block: the resident disk driver is already out of it
	long ring = (maxring < avail ? maxring : avail) & ~511L;
	if (ring < DMASTREAM_RING_MIN) return 0;
	s.ring = (unsigned char*)Malloc(ring);
	if (!s.ring || (long)s.ring < 0) { s.ring = 0; return 0; }
	s.ringsize = ring;
	s.probe = 0; s.quiet = 0;
	s.cidx = 6; while (s.cidx > 0 && g_dmastream_sizes[s.cidx] > ring / 3) --s.cidx;	// start at 32 KB (the biggest that fits the ring), the adaptation takes it from there
	s.base = s.cidx; s.chunk = g_dmastream_sizes[s.cidx];
#ifdef DMASTREAM_CHUNK
	s.chunk = DMASTREAM_CHUNK;
#endif
	s.flock = *(volatile short*)0x43e;
	if (s.raw) *(volatile short*)0x43e = 1;						// the floppy VBL code of TOS must leave the DMA chip alone
	if (!dmastream_begin()) return 0;
	return ring;
}

// music off / on (the file stays open; 'on' restarts from the beginning)
static void dmastream_pause() { DMA_CTRL = 0; g_dmastream.running = false; if (g_dmastream.pending) { dmraw_wait(1000000); g_dmastream.pending = false; } }
static bool dmastream_resume() { return g_dmastream.ring && g_dmastream.fh >= 0 && dmastream_begin(); }

static void dmastream_stop()
{
	dmastream_t& s = g_dmastream;
	DMA_CTRL = 0;
	s.running = false;
	if (s.pending) { dmraw_wait(1000000); s.pending = false; }
	if (g_dmraw.ok) { ACSI_MODE = 0x80; *(volatile short*)0x43e = s.flock; }
	if (s.fh >= 0) { Fclose(s.fh); s.fh = -1; }
	if (s.ring) { Mfree(s.ring); s.ring = 0; }
}

#endif // dmastream_h_
