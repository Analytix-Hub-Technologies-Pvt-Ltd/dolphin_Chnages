import React, { useState, useEffect, useMemo } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown, CheckCircle2, AlertCircle, X } from "lucide-react";
import { apiGet, apiPut } from "../../api/client";
import DolphinIconW from "../../assets/images/dolphin_w.png";

const MainLoader = () => (
  <div className="flex-1 flex flex-col justify-center items-center gap-4 min-h-[280px]">
    <img
      src={DolphinIconW}
      alt="Loading..."
      className="w-20 h-20 animate-swim"
    />
    <p className="text-text-secondary font-semibold animate-pulse text-sm">
      Loading members...
    </p>
  </div>
);

const ROLE_MAP = {
  1: "USER",
  2: "ADMIN",
  3: "SUPER_ADMIN",
};

const TABLE_COLUMNS = [
  { id: "name", label: "Name" },
  { id: "user_name", label: "Username" },
  { id: "email", label: "Email" },
  { id: "phone_number", label: "Phone Number" },
  { id: "company_name", label: "Company" },
  { id: "role", label: "Role in Company" },
  { id: "user_type", label: "User Type" },
  { id: "ship_name", label: "Ship Name" },
  { id: "ship_type", label: "Ship Type" },
  { id: "role_id", label: "Platform Role", align: "right" },
];

const Members = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [snackbarSeverity, setSnackbarSeverity] = useState("success");

  const [searchQuery, setSearchQuery] = useState("");
  const [sortConfig, setSortConfig] = useState({ key: "name", direction: "asc" });

  // Get current user details from local storage
  const userData = JSON.parse(localStorage.getItem("userData") || "{}");
  const profile = userData.user_profile || userData;
  const currentUserId = profile?.user_id;
  const currentUserRole = profile?.user_role;

  useEffect(() => {
    const timer = setTimeout(() => {
      let isMounted = true;

      const fetchUsers = async () => {
        setLoading(true);
        try {
          let url = `/users?admin_user_id=${currentUserId}&limit=100&offset=0`;
          if (searchQuery) {
            url += `&search=${encodeURIComponent(searchQuery)}`;
          }

          const data = await apiGet(url);
          if (!isMounted) return;

          if (data && data.users) {
            setUsers(data.users);
          } else if (Array.isArray(data)) {
            setUsers(data);
          } else {
            setUsers([]);
          }
        } catch (err) {
          if (!isMounted) return;
          setUsers([]);
          setSnackbarMessage(err.message || "Failed to load members.");
          setSnackbarSeverity("error");
        } finally {
          if (isMounted) {
            setLoading(false);
          }
        }
      };

      if (currentUserId) {
        fetchUsers();
      }

      return () => {
        isMounted = false;
      };
    }, 400);

    return () => clearTimeout(timer);
  }, [currentUserId, searchQuery]);

  useEffect(() => {
    if (!snackbarMessage) return;
    const timer = setTimeout(() => {
      setSnackbarMessage("");
    }, 4000);
    return () => clearTimeout(timer);
  }, [snackbarMessage]);

  const handleRoleChange = async (userId, newRoleId) => {
    try {
      await apiPut(`/users/${userId}/role?admin_user_id=${currentUserId}`, {
        role_id: Number(newRoleId),
      });

      setUsers((prevUsers) =>
        prevUsers.map((user) =>
          user.id === userId ? { ...user, role_id: Number(newRoleId) } : user
        )
      );

      setSnackbarMessage("Role updated successfully!");
      setSnackbarSeverity("success");
    } catch (err) {
      setSnackbarMessage(err.message || "Failed to update role.");
      setSnackbarSeverity("error");
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbarMessage("");
  };

  const handleReset = () => {
    setSearchQuery("");
  };

  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  const sortedUsers = useMemo(() => {
    let sortableUsers = [...users];
    if (sortConfig !== null) {
      sortableUsers.sort((a, b) => {
        let aValue = (a[sortConfig.key] || "").toString();
        let bValue = (b[sortConfig.key] || "").toString();

        if (sortConfig.key === "role_id") {
          aValue = ROLE_MAP[a.role_id] || "";
          bValue = ROLE_MAP[b.role_id] || "";
        }

        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();

        if (aValue < bValue) {
          return sortConfig.direction === "asc" ? -1 : 1;
        }
        if (aValue > bValue) {
          return sortConfig.direction === "asc" ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableUsers;
  }, [users, sortConfig]);

  return (
    <div className="min-h-full w-full max-w-full overflow-x-hidden bg-bg-default py-6">
      <div className="w-full max-w-full px-4 sm:px-6 lg:px-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-text-primary mb-6">
          Members Management
        </h1>

        {/* Filter Card */}
        <div className="bg-bg-paper p-6 mb-6 rounded-xl border border-border-default shadow-xs">
          <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-end">
            <div className="flex flex-col gap-1.5 min-w-full md:min-w-[300px]">
              <label className="text-xs font-medium text-text-secondary">
                Search Members
              </label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Name, Email, or Phone"
                className="w-full px-3 py-2 border border-border-default rounded-lg bg-bg-default text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all placeholder:text-text-secondary/60"
              />
            </div>

            <button
              type="button"
              onClick={handleReset}
              className="px-6 py-2 rounded-lg border border-primary text-primary hover:bg-primary/10 transition-colors font-medium text-sm cursor-pointer self-stretch md:self-auto"
            >
              Reset
            </button>
          </div>

          <p className="mt-4 text-xs text-text-secondary">
            {!loading && `Showing ${users.length} results`}
          </p>
        </div>

        {/* Table Container */}
        <div className="bg-bg-paper rounded-xl border border-border-default overflow-hidden w-full max-w-full shadow-xs">
          {loading ? (
            <MainLoader />
          ) : (
            <div className="w-full max-w-full overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[1050px]">
                <thead>
                  <tr className="bg-bg-lightblue1 dark:bg-bg-light border-b border-border-default">
                    {TABLE_COLUMNS.map((headCell) => {
                      const isActive = sortConfig.key === headCell.id;
                      return (
                        <th
                          key={headCell.id}
                          className={`py-3 px-4 text-sm font-semibold text-text-primary select-none whitespace-nowrap ${
                            headCell.align === "right" ? "text-right" : "text-left"
                          }`}
                        >
                          <button
                            type="button"
                            onClick={() => handleSort(headCell.id)}
                            className={`inline-flex items-center gap-1.5 hover:text-primary transition-colors cursor-pointer ${
                              headCell.align === "right" ? "ml-auto" : ""
                            }`}
                          >
                            <span>{headCell.label}</span>
                            {isActive ? (
                              sortConfig.direction === "asc" ? (
                                <ArrowUp className="w-3.5 h-3.5 text-primary" />
                              ) : (
                                <ArrowDown className="w-3.5 h-3.5 text-primary" />
                              )
                            ) : (
                              <ArrowUpDown className="w-3 h-3 opacity-30 group-hover:opacity-70" />
                            )}
                          </button>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {sortedUsers.length > 0 ? (
                    sortedUsers.map((user, idx) => (
                      <tr
                        key={user.id || idx}
                        className={`transition-colors hover:bg-bg-lightblue1 dark:hover:bg-bg-light ${
                          idx % 2 === 1
                            ? "bg-bg-light/30 dark:bg-transparent"
                            : "bg-transparent"
                        }`}
                      >
                        <td className="py-3 px-4 text-sm text-text-primary font-medium whitespace-nowrap">
                          {user.name || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-secondary whitespace-nowrap">
                          {user.user_name || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-secondary whitespace-nowrap">
                          {user.email || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-secondary whitespace-nowrap">
                          {user.phone_number || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-primary whitespace-nowrap">
                          {user.company_name || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-primary whitespace-nowrap">
                          {user.role || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-primary whitespace-nowrap">
                          {user.user_type || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-primary whitespace-nowrap">
                          {user.ship_name || "-"}
                        </td>
                        <td className="py-3 px-4 text-sm text-text-primary whitespace-nowrap">
                          {user.ship_type || "-"}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <select
                            value={user.role_id || 1}
                            disabled={
                              currentUserRole !== "SUPER_ADMIN" ||
                              user.id === currentUserId
                            }
                            onChange={(e) =>
                              handleRoleChange(user.id, e.target.value)
                            }
                            className="px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-border-default bg-bg-default text-text-primary disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer transition-all min-w-[120px]"
                          >
                            <option value={1}>USER</option>
                            <option value={2}>ADMIN</option>
                            <option value={3}>SUPER_ADMIN</option>
                          </select>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td
                        colSpan={10}
                        className="py-12 text-center text-sm text-text-secondary"
                      >
                        No members found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Snackbar Toast */}
      {snackbarMessage && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-lg border text-sm font-medium bg-bg-paper text-text-primary border-border-default">
          {snackbarSeverity === "error" ? (
            <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />
          ) : (
            <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
          )}
          <span>{snackbarMessage}</span>
          <button
            type="button"
            onClick={handleCloseSnackbar}
            className="ml-2 p-1 text-text-secondary hover:text-text-primary rounded-md cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};

export default Members;
