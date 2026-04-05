import React, {useEffect, useState} from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import ExerciseDetail from 'src/pages/ExerciseDetail';
import Exercises from 'src/pages/Exercises';
import Home from 'src/pages/Home';
import Logs from 'src/pages/Logs';
import HomeParticipant from 'src/pages/participant/Home';
import HomeClient from 'src/pages/client/Home';
import {useKeycloak} from '@react-keycloak/web';
import {LogProvider} from 'src/contexts/LogContext';
import {useDispatch} from 'react-redux';
import {Intent, Spinner, SpinnerSize} from '@blueprintjs/core';
import ParticipantExercises from './pages/participant/Exercises';
import DeploymentDetail from './pages/DeploymentDetail';
import ParticipantDeploymentDetail from './pages/participant/DeploymentDetail';
import {UserRole} from './models/userRoles';
import useDefaultRoleSelect from './hooks/useDefaultRoleSelect';
import ScoreDetail from './pages/ScoreDetail';
import DeploymentFocus from './pages/DeploymentFocus';
import RolesFallback from './pages/RolesFallback';
import {setToken} from './slices/userSlice';
import MainNavbar from './components/Navbar/MainNavBar';
import ManagerNavbarLinks from './components/Navbar/ManagerLinks';
import ParticipantNavbarLinks from './components/Navbar/ParticipantLinks';
import NotFoundFallback from './pages/NotFoundFallback';
import ManagerOrders from './pages/Orders';
import AdminOrderFetcher from './pages/OrderFetcher';
import ClientOrderFetcher from './pages/client/OrderFetcher';
import ClientNavbarLinks from './components/Navbar/ClientLinks';

const App = () => {
  const {keycloak, keycloak: {authenticated, token}} = useKeycloak();
  const dispatch = useDispatch();
  const currentRole = useDefaultRoleSelect();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token !== undefined) {
      dispatch(setToken(token));
    }
  }, [token, dispatch]);

  useEffect(() => {
    keycloak.onTokenExpired = () => {
      keycloak.updateToken(180).then(refreshed => {
        if (refreshed && keycloak.token) {
          dispatch(setToken(keycloak.token));
        }
      }).catch(() => {
        keycloak.clearToken();
      });
    };

    keycloak.onAuthRefreshError = async () => {
      keycloak.clearToken();
    };
  }, [
    keycloak,
    keycloak.token,
    dispatch,
  ]);

  useEffect(() => {
    if (authenticated && currentRole !== undefined) {
      setLoading(false);
    }
  }, [authenticated, currentRole]);

  if (loading) {
    return (
      <div className='flex justify-center items-center h-screen'>
        <Spinner size={SpinnerSize.LARGE} intent={Intent.PRIMARY}/>
      </div>
    );
  }

  if (authenticated && (currentRole === UserRole.MANAGER)) {
    return (
      <LogProvider>
        <Router>
          <MainNavbar navbarLinks={<ManagerNavbarLinks/>}/>
          <Routes>
            <Route path='/' element={<Home/>}/>
            <Route path='/exercises' element={<Exercises/>}/>
            <Route path='/logs' element={<Logs/>}/>
            <Route path='/exercises/:exerciseId' element={<ExerciseDetail/>}/>
            <Route
              path='/exercises/:exerciseId/deployments/:deploymentId'
              element={<DeploymentDetail/>}/>
            <Route
              path='/exercises/:exerciseId/deployments/:deploymentId/focus'
              element={<DeploymentFocus/>}/>
            <Route
              path='/exercises/:exerciseId/deployments/:deploymentId/scores/:role'
              element={<ScoreDetail/>}/>
            <Route path='/orders' element={<ManagerOrders/>}/>
            <Route path='/orders/:orderId' element={<AdminOrderFetcher/>}/>
            <Route path='/orders/:orderId/:stage' element={<AdminOrderFetcher/>}/>
            <Route path='/*' element={<NotFoundFallback/>}/>
          </Routes>
        </Router>
      </LogProvider>
    );
  }

  if (authenticated && (currentRole === UserRole.PARTICIPANT)) {
    return (
      <Router>
        <MainNavbar navbarLinks={<ParticipantNavbarLinks/>}/>
        <Routes>
          <Route path='/' element={<HomeParticipant/>}/>
          <Route path='/exercises' element={<ParticipantExercises/>}/>
          <Route
            path='/exercises/:exerciseId/deployments/:deploymentId'
            element={<ParticipantDeploymentDetail/>}/>
          <Route path='/*' element={<NotFoundFallback/>}/>
        </Routes>
      </Router>
    );
  }

  if (authenticated && (currentRole === UserRole.CLIENT)) {
    return (
      <Router>
        <MainNavbar navbarLinks={<ClientNavbarLinks/>}/>
        <Routes>
          <Route path='/' element={<HomeClient/>}/>
          <Route path='/*' element={<NotFoundFallback/>}/>
          <Route path='/orders/:orderId' element={<ClientOrderFetcher/>}/>
          <Route path='/orders/:orderId/:stage' element={<ClientOrderFetcher/>}/>
        </Routes>
      </Router>
    );
  }

  if (authenticated && (currentRole === undefined)) {
    return (
      <Router>
        <MainNavbar/>
        <Routes>
          <Route path='/' element={<RolesFallback/>}/>
          <Route path='/*' element={<Navigate replace to='/'/>}/>
        </Routes>
      </Router>
    );
  }

  return null;
};

export default App;
