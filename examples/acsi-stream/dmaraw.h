//======================================================================================================================
//	dmaraw.h - non blocking disk reads through the ACSI DMA (MIT, see docs/11-acsi-streaming.md)
//----------------------------------------------------------------------------------------------------------------------
//	GEMDOS Fread blocks the CPU until the disk driver has moved the data: ~20 ms for 16 KB, i.e. a lost frame. The ACSI
//	DMA chip can do the transfer by itself, so:
//	- a command READ is sent to the drive by hand: ICD READ(10) (byte $1f + id<<5, then the SCSI command, works with an
//	  UltraSatan or an ICD adapter, any LBA) or the classic ACSI READ(6) (first 1 GB only). sending takes some 100 us
//	- the last command byte starts the DMA: the CPU goes on working, the chip writes the sectors into RAM by itself
//	- the end of the command is seen on the MFP GPIP bit 5 (HDC interrupt line, low = done), polled one frame later, then
//	  the status byte is read ($ff8606 = $8a, read $ff8604)
//	for this the file must be stored in consecutive sectors (defragmented). its position on the disk is found without parsing the FAT:
//	hdv_rw ($476, the BIOS read/write vector) is hooked during a GEMDOS Fread and the arguments of the Rwabs call that reads the
//	file are copied, giving the logical sector and the drive. the drive's ACSI id and partition start come from PUN_INFO ($516,
//	every HD driver incl. HDDRIVER provides it). this is verified: contiguity is checked at several places of the file and a
//	sector read with the DMA must be identical to what Fread returned.
//	NOTHING in here is used if one check fails: dmastream.h then uses plain Fread.
//----------------------------------------------------------------------------------------------------------------------
#ifndef dmaraw_h_
#define dmaraw_h_

#define ACSI_DATA16	(*(volatile unsigned short*)0xffff8604)
#define ACSI_DATA32	(*(volatile unsigned long*)0xffff8604)
#define ACSI_MODE	(*(volatile unsigned short*)0xffff8606)
#define ACSI_ADRH	(*(volatile unsigned char*)0xffff8609)
#define ACSI_ADRM	(*(volatile unsigned char*)0xffff860b)
#define ACSI_ADRL	(*(volatile unsigned char*)0xffff860d)
#define MFP_GPIP	(*(volatile unsigned char*)0xfffffa01)

// ---- hdv_rw hook: copies the arguments of the first Rwabs call whose buffer is 'dmraw_hooktarget'
extern "C"
{
	volatile unsigned long dmraw_hookbuf[8] __attribute__((used));		// stack copy: +0 return, +4 rwflag.w, +6 buf.l, +10 count.w, +12 recno.w, +14 dev.w, +16 lrecno.l
	volatile unsigned long dmraw_hookorig __attribute__((used));
	volatile unsigned long dmraw_hooktarget __attribute__((used));
	volatile unsigned char dmraw_hookflag __attribute__((used));
}
extern "C" __attribute__((naked, used, noinline)) void dmraw_hook()
{
	__asm__ volatile(
		"tst.b	_dmraw_hookflag\n\t"
		"bne.s	1f\n\t"
		"move.l	6(%sp),%a0\n\t"
		"cmp.l	_dmraw_hooktarget,%a0\n\t"
		"bne.s	1f\n\t"
		"st	_dmraw_hookflag\n\t"
		"move.l	%sp,%a0\n\t"
		"lea	_dmraw_hookbuf,%a1\n\t"
		"move.l	(%a0)+,(%a1)+\n\tmove.l	(%a0)+,(%a1)+\n\tmove.l	(%a0)+,(%a1)+\n\tmove.l	(%a0)+,(%a1)+\n\t"
		"move.l	(%a0)+,(%a1)+\n\tmove.l	(%a0)+,(%a1)+\n\tmove.l	(%a0)+,(%a1)+\n\tmove.l	(%a0)+,(%a1)+\n"
		"1:\n\t"
		"move.l	_dmraw_hookorig,%a0\n\t"
		"jmp	(%a0)\n\t");
}

static inline unsigned dmraw_w(const volatile unsigned char *p) { return ((unsigned)p[0] << 8) | p[1]; }
static inline unsigned long dmraw_l(const volatile unsigned char *p) { return ((unsigned long)p[0] << 24) | ((unsigned long)p[1] << 16) | ((unsigned long)p[2] << 8) | p[3]; }

// BIOS Getbpb(dev): returns the BPB pointer (first word = bytes per logical sector), 0 if it fails
static long dmraw_getbpb(short dev)
{
	register long ret __asm__("d0");
	__asm__ volatile(
		"move.w	%1,-(%%sp)\n\t"
		"move.w	#7,-(%%sp)\n\t"
		"trap	#13\n\t"
		"addq.l	#4,%%sp"
		: "=d"(ret) : "d"(dev) : "d1", "d2", "a0", "a1", "a2", "memory", "cc");
	return ret;
}

// ---- the ACSI command layer
static inline bool dmraw_wait_irq(long tmo)								// HDC interrupt = GPIP bit 5 low
{
	while (MFP_GPIP & 0x20) if (--tmo <= 0) return false;
	return true;
}
static inline bool dmraw_putbyte(unsigned char b, unsigned short nextmode, long tmo)
{
	ACSI_DATA32 = ((unsigned long)b << 16) | nextmode;				// one long write = data word to $ff8604, then mode word to $ff8606
	return dmraw_wait_irq(tmo);
}

// start reading 'n' sectors (1..255, 512 bytes each) from physical sector 'lba' into 'buf' (even address). returns false if the drive doesn't answer.
// the DMA then runs by itself: dmraw_poll() tells when it is finished
static bool dmraw_start(unsigned char *buf, unsigned long lba, int n, bool icd, unsigned char idbits, long tmo)
{
	unsigned long a = (unsigned long)buf;
	ACSI_ADRL = (unsigned char)a; ACSI_ADRM = (unsigned char)(a >> 8); ACSI_ADRH = (unsigned char)(a >> 16);
	ACSI_MODE = 0x198; ACSI_MODE = 0x098;						// toggle the DMA direction bit: read (disk -> RAM), then select the sector count register
	ACSI_DATA16 = (unsigned short)n;
	ACSI_MODE = 0x088;									// command register, A0 = 0 (first byte)
	bool ok;
	if (icd)												// ICD: $1f escape, then the 10 byte SCSI command READ(10)
		ok = dmraw_putbyte(0x1f | idbits, 0x8a, tmo) && dmraw_putbyte(0x28, 0x8a, tmo) && dmraw_putbyte(0, 0x8a, tmo)
			&& dmraw_putbyte((unsigned char)(lba >> 24), 0x8a, tmo) && dmraw_putbyte((unsigned char)(lba >> 16), 0x8a, tmo)
			&& dmraw_putbyte((unsigned char)(lba >> 8), 0x8a, tmo) && dmraw_putbyte((unsigned char)lba, 0x8a, tmo)
			&& dmraw_putbyte(0, 0x8a, tmo) && dmraw_putbyte(0, 0x8a, tmo) && dmraw_putbyte((unsigned char)n, 0x8a, tmo);
	else													// classic ACSI READ(6)
		ok = dmraw_putbyte(0x08 | idbits, 0x8a, tmo) && dmraw_putbyte((unsigned char)(lba >> 16) & 0x1f, 0x8a, tmo)
			&& dmraw_putbyte((unsigned char)(lba >> 8), 0x8a, tmo) && dmraw_putbyte((unsigned char)lba, 0x8a, tmo)
			&& dmraw_putbyte((unsigned char)n, 0x8a, tmo);
	if (!ok) { ACSI_MODE = 0x80; return false; }
	ACSI_DATA32 = 0x0000000aUL;								// last byte (control = 0), mode $0a: the command executes and the DMA starts
	return true;
}

// 0 = still running, 1 = finished OK, -1 = finished with an error status
static int dmraw_poll()
{
	if (MFP_GPIP & 0x20) return 0;
	ACSI_MODE = 0x8a;
	unsigned short st = ACSI_DATA16 & 0xff;							// status byte: reading it ends the command
	ACSI_MODE = 0x80;
	return st == 0 ? 1 : -1;
}
static int dmraw_wait(long spins)
{
	int r;
	while ((r = dmraw_poll()) == 0) if (--spins <= 0) { ACSI_MODE = 0x80; return -1; }
	return r;
}

// ---- finding the file on the disk
struct dmraw_t
{
	bool		ok;
	bool		icd;
	unsigned char	idbits;
	short		dev;
	unsigned long	lba0;											// physical sector (512 bytes) of the first byte of the file
	short		state;											// result of the probe: 1 ICD ok, 2 ACSI6 ok, <0 = reason of the failure
};
static dmraw_t g_dmraw = { false, true, 0, 0, 0, 0 };
static unsigned char g_dmraw_sec[512 + 16] __attribute__((aligned(4)));

// locate the open file 'fh' (first 'len' bytes are meaningful) and check that raw reads give the same bytes as Fread.
// 'tmp' = 32 KB scratch buffer. sets g_dmraw. state: -1 no PUN_INFO, -2 hook captured nothing, -3 not a hard disk driver unit,
// -4 not contiguous, -5 raw read doesn't match, -6 bad BPB
static bool dmraw_probe(short fh, long len, unsigned char *tmp)
{
	dmraw_t& r = g_dmraw;
	r.ok = false;
	const unsigned long pun = *(volatile unsigned long*)0x516;
	if (!pun || (pun & 1) || pun >= 0x400000) { r.state = -1; return false; }
	const unsigned char *pun_b = (const unsigned char*)pun;
	const long TMPLEN = 32768;
	long probe[4]; int np = 0;
	probe[np++] = 0;
	for (int k = 1; k <= 3; ++k) { long o = ((len / 4) * k) & ~65535L; if (o > 0 && o + 512 <= len) probe[np++] = o; }
	{ long o = (len - TMPLEN) & ~65535L; if (o > probe[np - 1] && o + 512 <= len && np < 4) probe[np++] = o; }
	unsigned long logical0 = 0; unsigned long recsiz = 0; short dev = -1; unsigned long start = 0;
	for (int i = 0; i < np; ++i)
	{
		if (Fseek(probe[i], fh, 0) != probe[i]) { r.state = -2; return false; }
		dmraw_hookflag = 0; dmraw_hooktarget = (unsigned long)tmp;
		dmraw_hookorig = *(volatile unsigned long*)0x476;
		*(volatile unsigned long*)0x476 = (unsigned long)dmraw_hook;
		long got = Fread(fh, TMPLEN, tmp);
		*(volatile unsigned long*)0x476 = dmraw_hookorig;
		if (!dmraw_hookflag || got < 512) { r.state = -2; return false; }
		unsigned rwflag = dmraw_w((const volatile unsigned char*)dmraw_hookbuf + 4), recno = dmraw_w((const volatile unsigned char*)dmraw_hookbuf + 12);
		short d = (short)dmraw_w((const volatile unsigned char*)dmraw_hookbuf + 14);
		unsigned long lrec = recno == 0xffff ? dmraw_l((const volatile unsigned char*)dmraw_hookbuf + 16) : recno;
		if (rwflag & 1) { r.state = -2; return false; }
		if (i == 0)
		{
			dev = d; logical0 = lrec;
			if (dev < 0 || dev >= 16 || (pun_b[2 + dev] & 0x90) || pun_b[2 + dev] == 0xff) { r.state = -3; return false; }	// bit 7: not an HD, bit 4: IDE
			long bpb = dmraw_getbpb(dev);
			if (bpb <= 0 || (bpb & 1)) { r.state = -6; return false; }
			recsiz = dmraw_w((const volatile unsigned char*)bpb);
			if (recsiz < 512 || (recsiz & 511) || recsiz > 8192) { r.state = -6; return false; }
			start = dmraw_l((const volatile unsigned char*)pun + 18 + 4 * dev);
			r.dev = dev; r.idbits = (unsigned char)((pun_b[2 + dev] & 7) << 5);
			r.lba0 = start + logical0 * (recsiz / 512);
		}
		else if (d != dev || lrec != logical0 + (unsigned long)probe[i] / recsiz) { r.state = -4; return false; }	// fragmented
		// the same data through the DMA (first time: find out whether the drive takes ICD commands)
		unsigned long lba = r.lba0 + (unsigned long)probe[i] / 512;
		bool ok = false;
		const int nt = i == 0 ? 2 : 1;
		for (int t = 0; t < nt && !ok; ++t)
		{
			bool icd = i == 0 ? (t == 0) : r.icd;
			if (!icd && lba >= (1UL << 21)) continue;
			for (int k = 0; k < 512; ++k) g_dmraw_sec[k] = (unsigned char)~tmp[k];
			if (dmraw_start(g_dmraw_sec, lba, 1, icd, r.idbits, 40000) && dmraw_wait(3000000) > 0)
			{
				bool same = true; for (int k = 0; k < 512; ++k) if (g_dmraw_sec[k] != tmp[k]) { same = false; break; }
				if (same) { ok = true; r.icd = icd; r.state = icd ? 1 : 2; }
			}
		}
		if (!ok) { r.state = -5; return false; }
	}
	r.ok = true;
	return true;
}

#endif // dmaraw_h_
