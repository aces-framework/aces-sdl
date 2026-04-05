import {Intent, OverlayToaster, Position} from '@blueprintjs/core';

export const AppToaster = OverlayToaster.create({
  className: 'recipe-toaster',
  position: Position.TOP,
  maxToasts: 3,
  // eslint-disable-next-line unicorn/prefer-query-selector
}, document.getElementById('toast') ?? undefined);

export const toastSuccess = (message: string) => (
  AppToaster.show({
    icon: 'tick',
    intent: Intent.SUCCESS,
    message: `${message}`,
  })
);

export const toastWarning = (message: string) => (
  AppToaster.show({
    icon: 'warning-sign',
    intent: Intent.DANGER,
    message: `${message}`,
  })
);
