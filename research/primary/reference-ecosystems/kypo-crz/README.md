> The code from this repository has been integrated to the [frontend-platform monorepo](https://github.com/cyberrangecz/frontend-platform), where development and maintenance continue.

# Adaptive Model Simulator

This project is a simulator for adaptive training runs. It allows to predict the behavior of a training run, based on relevant factors. Secondly, it contains visualizations for the training runs and the task difficulties generated.

## Running the demo app locally

1. Pull and run the [Adaptive training service](https://github.com/cyberrangecz/backend-adaptive-training) or the whole [deployment](https://github.com/cyberrangecz/devops-helm).
2. Install dependencies by running `npm install`.
3. Configure [environment.local.ts](projects/adaptive-instance-simulator-example-app/src/environments/environment.local.ts), pointing to the Adaptive training service.
4. Run the project by running `npm run start`.
5. Navigate to `https://localhost:4200/`. The app will automatically reload if you change any of the source files. The app will be running with self-signed certificate, so you will need to accept the security exception in the browser.

## Code scaffolding

Run `ng generate component component-name` to generate a new component. You can also use `ng generate directive|pipe|service|class|guard|interface|enum|module`.

## Build library

Run `npm run build-and-pack` to build and pack the project. The build artifacts and package will be stored in the `dist/` directory.

## Running unit tests

Run `ng test` to execute the unit tests via [Karma](https://karma-runner.github.io).
