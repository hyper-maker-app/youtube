import React from 'react';
import {Composition} from 'remotion';
import {GeospatialStormMap} from './compositions/GeospatialStormMap';
import {TelemetryCurve} from './compositions/TelemetryCurve';
import {VolcanoSeismicMap} from './compositions/VolcanoSeismicMap';
import {GeospatialStormMapProps, TelemetryCurveProps, VolcanoSeismicMapProps} from './types';
import {validatePayload} from './utils/payload';

// Production compositions have no scenario defaults. Supply a complete JSON payload.
export const RemotionRoot: React.FC = () => <>
  <Composition id="GeospatialStormMap" component={GeospatialStormMap}
    durationInFrames={480} fps={60} width={1920} height={1080}
    defaultProps={{} as GeospatialStormMapProps}
    calculateMetadata={({props}) => ({props: validatePayload('GeospatialStormMap', props)})} />
  <Composition id="TelemetryCurve" component={TelemetryCurve}
    durationInFrames={360} fps={60} width={1920} height={1080}
    defaultProps={{} as TelemetryCurveProps}
    calculateMetadata={({props}) => ({props: validatePayload('TelemetryCurve', props)})} />
  <Composition id="VolcanoSeismicMap" component={VolcanoSeismicMap}
    durationInFrames={480} fps={60} width={1920} height={1080}
    defaultProps={{} as VolcanoSeismicMapProps}
    calculateMetadata={({props}) => ({props: validatePayload('VolcanoSeismicMap', props)})} />
</>;
