import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import webCase from '../../docs/assets/screenshots/web-case.png';
import webEvidence from '../../docs/assets/screenshots/web-evidence.png';
import webTrace from '../../docs/assets/screenshots/web-trace.png';
import hermesTui from '../../docs/assets/screenshots/hermes-tui.png';

const colors = {
  canvas: '#faf6f2',
  ink: '#251d1b',
  rose: '#c94262',
  clay: '#986549',
  mint: '#dff1e8',
  line: '#e4d5cd',
};

const base: React.CSSProperties = {
  fontFamily: 'Inter, Avenir Next, system-ui, sans-serif',
  color: colors.ink,
};

const Scene: React.FC<React.PropsWithChildren<{label: string; dark?: boolean}>> = ({label, dark, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 18}});
  return (
    <AbsoluteFill
      style={{
        ...base,
        background: dark ? '#181210' : colors.canvas,
        color: dark ? '#fff8f1' : colors.ink,
        padding: 92,
        opacity: interpolate(frame, [0, 12], [0, 1], {extrapolateRight: 'clamp'}),
      }}
    >
      <div style={{fontSize: 26, letterSpacing: 4, textTransform: 'uppercase', color: dark ? '#d7aa95' : colors.rose}}>{label}</div>
      <div style={{transform: `translateY(${(1 - enter) * 34}px)`, flex: 1, display: 'flex'}}>{children}</div>
    </AbsoluteFill>
  );
};

const Title: React.FC<{children: React.ReactNode; width?: number}> = ({children, width = 1450}) => (
  <div style={{fontSize: 92, lineHeight: 1.02, fontWeight: 800, maxWidth: width, letterSpacing: -4}}>{children}</div>
);

const Pill: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div style={{padding: '16px 24px', borderRadius: 999, background: colors.mint, color: '#28664b', fontSize: 28, fontWeight: 700}}>{children}</div>
);

const Shot: React.FC<{src: string; offset?: number}> = ({src, offset = 0}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 360], [1.04 + offset, 1 + offset], {extrapolateRight: 'clamp'});
  return (
    <div style={{borderRadius: 26, overflow: 'hidden', border: `2px solid ${colors.line}`, boxShadow: '0 30px 80px #4a2d2028', width: '100%', height: 760}}>
      <Img src={src} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${scale})`}} />
    </div>
  );
};

const Architecture: React.FC = () => {
  const frame = useCurrentFrame();
  const steps = ['Address', 'Approved fields', 'Unit treatment', 'Code route', 'Trace', 'Hermes'];
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 20, width: '100%', marginTop: 90}}>
      {steps.map((step, index) => {
        const visible = interpolate(frame, [index * 24, index * 24 + 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return (
          <React.Fragment key={step}>
            <div style={{opacity: visible, transform: `translateY(${(1 - visible) * 25}px)`, padding: '30px 24px', borderRadius: 18, background: index === 5 ? '#f5e8ba' : '#fff', border: `2px solid ${colors.line}`, fontSize: 29, fontWeight: 750, textAlign: 'center', flex: 1}}>{step}</div>
            {index < steps.length - 1 ? <div style={{fontSize: 42, color: colors.clay, opacity: visible}}>→</div> : null}
          </React.Fragment>
        );
      })}
    </div>
  );
};

const EvalRows: React.FC = () => {
  const frame = useCurrentFrame();
  const rows = ['Installed command', 'Hermes TUI contract', 'Fixture and trace', 'Loopback refusal', 'WebSocket round trip'];
  return (
    <div style={{display: 'grid', gap: 18, width: 880, marginTop: 42}}>
      {rows.map((row, index) => {
        const enter = interpolate(frame, [index * 18, index * 18 + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return <div key={row} style={{opacity: enter, display: 'flex', justifyContent: 'space-between', padding: '22px 28px', borderRadius: 16, background: '#fff', border: `2px solid ${colors.line}`, fontSize: 30}}><span>{row}</span><strong style={{color: '#2f805c'}}>PASS</strong></div>;
      })}
    </div>
  );
};

export const ShakiSevaDay0: React.FC = () => (
  <AbsoluteFill style={base}>
    <Audio src={staticFile('narration.wav')} />

    <Sequence durationInFrames={180}>
      <Scene label="Day 0">
        <div style={{display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 34}}>
          <Title>Public records, treated with care.</Title>
          <div style={{fontSize: 42, color: colors.clay}}>Shaki Seva Studio</div>
        </div>
      </Scene>
    </Sequence>

    <Sequence from={180} durationInFrames={390}>
      <Scene label="The product rule">
        <div style={{display: 'flex', flexDirection: 'column', justifyContent: 'center', width: '100%'}}>
          <Title width={1600}>Code decides what the records say. Hermes explains the bounded packet.</Title>
          <Architecture />
        </div>
      </Scene>
    </Sequence>

    <Sequence from={570} durationInFrames={420}>
      <Scene label="Hermes interface" dark>
        <div style={{display: 'grid', gridTemplateColumns: '480px 1fr', gap: 60, alignItems: 'center', width: '100%'}}>
          <div><Title width={460}>A real TUI at 32K.</Title><p style={{fontSize: 34, lineHeight: 1.35, color: '#d7c4bb'}}>The wrapper sets the evaluated startup floor and keeps compression available.</p></div>
          <Shot src={hermesTui} />
        </div>
      </Scene>
    </Sequence>

    <Sequence from={990} durationInFrames={390}>
      <Scene label="Local web app">
        <div style={{display: 'grid', gridTemplateColumns: '1fr 540px', gap: 60, alignItems: 'center', width: '100%'}}>
          <Shot src={webCase} />
          <div><Title width={520}>One building. One timeline.</Title><div style={{display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 38}}><Pill>Loopback only</Pill><Pill>Same origin socket</Pill></div></div>
        </div>
      </Scene>
    </Sequence>

    <Sequence from={1380} durationInFrames={450}>
      <Scene label="Evidence and trace">
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, alignItems: 'center', width: '100%'}}>
          <Shot src={webEvidence} />
          <Shot src={webTrace} />
        </div>
      </Scene>
    </Sequence>

    <Sequence from={1830} durationInFrames={510}>
      <Scene label="Repeatable proof">
        <div style={{display: 'grid', gridTemplateColumns: '1fr 900px', gap: 80, alignItems: 'center', width: '100%'}}>
          <div><Title width={740}>Day 0 means visible limits.</Title><p style={{fontSize: 34, lineHeight: 1.4, color: colors.clay}}>Bonsai reviewed the plan. Unsupported claims were rejected. Liquid Audio made the local narration.</p></div>
          <EvalRows />
        </div>
      </Scene>
    </Sequence>
  </AbsoluteFill>
);
