import React from 'react';
import {Composition} from 'remotion';
import {ShakiSevaDay0} from './video';

export const Root: React.FC = () => (
  <Composition
    id="ShakiSevaDay0"
    component={ShakiSevaDay0}
    durationInFrames={2340}
    fps={30}
    width={1920}
    height={1080}
  />
);
