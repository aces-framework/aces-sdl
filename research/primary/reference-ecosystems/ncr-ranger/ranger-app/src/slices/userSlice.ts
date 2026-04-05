import {type PayloadAction, createSlice} from '@reduxjs/toolkit';
import {type UserRole} from 'src/models/userRoles';
import {type RootState} from 'src/store';

const initialState: {
  token?: string;
  roles: UserRole[];
  selectedRole?: UserRole;
  roleSelected?: boolean;
  selectedEntity?: string;
} = {
  roles: [],
  roleSelected: false,
  selectedRole: undefined,
};

export const userSlice = createSlice({
  name: 'user',
  initialState,
  reducers: {
    setToken(state, action: PayloadAction<string>) {
      state.token = action.payload;
    },
    setRoles(state, action: PayloadAction<UserRole[]>) {
      state.roles = action.payload;
    },
    selectRole(state, action: PayloadAction<UserRole | undefined>) {
      state.selectedRole = action.payload;
      state.roleSelected = true;
    },
    setSelectedEntity(state, action: PayloadAction<string | undefined>) {
      state.selectedEntity = action.payload;
    },
  },
});

export const {setToken, setRoles, selectRole, setSelectedEntity} = userSlice.actions;

export const selectedRoleSelector = (state: RootState) =>
  state.user.selectedRole;
export const roleSelectedSelector = (state: RootState) =>
  state.user.roleSelected;
export const rolesSelector = (state: RootState) => state.user.roles;
export const selectedEntity = (state: RootState) => state.user.selectedEntity;
export const tokenSelector = (state: RootState) => state.user.token;
